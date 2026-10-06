"""CAUSYN ASGI website. Run python web_app.py; analysis stays in isolated workers."""
import argparse
import contextlib
import hmac
from contextlib import asynccontextmanager
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from deployment_config import WebSettings, runtime_path
from web_access import create_access_store
from guided_investigations import GUIDES, guided_question

ROOT=Path(__file__).resolve().parent
UI=ROOT/'ui'
JOBS={}
PROCESSES={}
JOB_OWNERS={}
JOB_CREATED={}
LOCK=threading.Lock()
PRESETS={
 'comparison':{'question':'Compare November 2017 with December 2017. Report merchandise value, order-count change and late-delivery-rate difference.'},
 'waterfall':{'question':'Create a waterfall chart from November 2017 to December 2017, splitting the merchandise-value change into order-volume and average-order-value contributions.'},
 'definition':{'question':'How is late delivery defined?'},
 'categories':{'question':'Show the leading categories by delivered merchandise value for November through December 2017.'},
}


def demo_result(kind):
    question=PRESETS[kind]['question']
    args={'baseline_month':'2017-11','comparison_month':'2017-12'}
    common={'question':question,'is_demo':True,'claims':[], 'artifacts':[],
        'ai_review':{'verdict':'EXAMPLE','limitation':'Recorded example, not a new model review.'},
        'numerical_check':{'status':'EXAMPLE'},'evidence_check':{'status':'EXAMPLE'},
        'citation_check':{'status':'EXAMPLE'},'chart_check':{'status':'EXAMPLE'},
        'usage':{'api_requests':0,'elapsed_seconds':0,'estimated_cost_usd':'0','usage_complete':True},
        'agent_trace':[]}
    if kind=='definition':
        common['answer']='A **late delivery** occurs when the actual customer delivery calendar date is later than the estimated delivery calendar date.\n\nThis compares calendar dates, rather than the exact time of day.\n\n[docs/metric_dictionary.md | metric-05 | Late delivery]'
        common['evidence']=[{'tool':'search_metric_dictionary','arguments':{'query':'late delivery definition'},'result':{'matches':[{'source':'docs/metric_dictionary.md','section_id':'metric-05','section':'Late delivery','passage':'Actual customer delivery calendar date is later than the estimated delivery calendar date.'}]}}]
    elif kind=='categories':
        common['answer']='## Leading categories\n\nFor November through December 2017, the leading categories by delivered merchandise value were:\n\n- **Watches and gifts:** R$164,849.26\n- **Health and beauty:** R$138,963.15\n- **Bed, bath and table:** R$138,038.79\n\nThe period included 12,802 delivered orders and R$1,713,798.56 in merchandise value across all categories. This is a recorded example, not a new query. Merchandise excludes freight and is not profit or corporate revenue. Source: analytics.category_monthly + analytics.monthly_performance.'
        common['evidence']=[{'tool':'get_category_performance','arguments':{'start_month':'2017-11','end_month':'2017-12'},'result':{
            'start_month':'2017-11','end_month':'2017-12','currency':'BRL',
            'source':'analytics.category_monthly + analytics.monthly_performance',
            'reference':{'delivered_orders':12802,'delivered_merchandise_value':'1713798.56'},
            'rows':[{'category_label':label,'merchandise_value':value} for label,value in [
                ('watches_gifts','164849.26'),('health_beauty','138963.15'),('bed_bath_table','138038.79')]],
            'interpretation':'Three leading categories in this recorded example. Other categories are included in the period totals but not plotted. Category order counts overlap; merchandise value is not profit.'}}]
    elif kind=='comparison':
        common['answer']='## A quieter December\n\nDelivered merchandise value fell **26.50%**, from **R$987,765.37** in November to **R$726,033.19** in December 2017.\n\n- **1,776 fewer delivered orders**\n- Late-delivery rate improved by **4.95 percentage points**\n\nThese are delivered orders grouped by purchase month. Merchandise value excludes freight and represents neither profit nor corporate revenue. Currency: BRL.\n\nThe figures describe what changed; they do not prove why it happened. Source: analytics.monthly_performance.'
        common['evidence']=[{'tool':'compare_months','arguments':args,'result':{**args,'currency':'BRL','source':'analytics.monthly_performance','baseline_merchandise_value':'987765.37','comparison_merchandise_value':'726033.19','change_value':'-261732.18','change_pct':'-26.4974039330818','order_count_change':-1776,'late_delivery_change_percentage_points':'-4.94884558860277'}}]
    else:
        common['answer']='## The shape of the decline\n\nThe **R$261,732.18** fall in delivered merchandise value splits into:\n\n- **R$237,281.84** from the change in order volume\n- **R$24,450.34** from the change in average order value\n\nBoth contributions reconcile to the total change. This symmetric allocation is an arithmetic breakdown, not proof of causes.\n\nScope: delivered orders grouped by purchase month, November → December 2017. Currency: BRL. Merchandise excludes freight and is not profit or corporate revenue. Source: analytics.monthly_performance.'
        common['evidence']=[{'tool':'decompose_merchandise_change','arguments':args,'result':{**args,'currency':'BRL','source':'analytics.monthly_performance','baseline_merchandise_value':'987765.37','comparison_merchandise_value':'726033.19','change_value':'-261732.18','volume_effect':'-237281.84','average_value_effect':'-24450.34','reconciled':True}}]
    return common


def worker():
    """JSON-lines protocol. API key and database configuration stay in Python."""
    output=sys.stdout
    def emit(event):
        output.write(json.dumps(event,default=lambda value: format(value, 'f') if isinstance(value, Decimal) else str(value))+'\n');output.flush()
    try:
        request=json.loads(sys.stdin.readline())
        with contextlib.redirect_stdout(io.StringIO()):
            import agent
            original=agent.request_interaction
            def instrument(client,requests,**kwargs):
                role=kwargs.get('agent_name','orchestrator')
                emit({'type':'progress','role':role,'status':'running','request':len(requests)+1})
                response=original(client,requests,**kwargs)
                emit({'type':'progress','role':role,'status':'done','request':len(requests)})
                return response
            agent.request_interaction=instrument
            result=agent.answer_question(request['question'])
        result['is_demo']=False
        emit({'type':'result','result':result})
    except Exception as error:
        review=getattr(error,'review',None)
        if review:
            message='The evidence reviewer blocked this draft. Try a more specific question.'
        elif isinstance(error,(ValueError,RuntimeError)):
            message=str(error)
        else:
            message='Live analysis could not complete. Check the project dependencies, database connection and API configuration in your terminal.'
        emit({'type':'error','message':message,'review':review})


def run_job(job_id,request,access=None):
    process=None
    try:
        if request['mode']=='demo':
            result=demo_result(request['demo_id'])
            with LOCK:JOBS[job_id].update(status='complete',result=result)
            return
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],
            cwd=str(ROOT),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        with LOCK:PROCESSES[job_id]=process
        process.stdin.write(json.dumps({'question':request['question']})+'\n');process.stdin.close()
        timeout=threading.Timer(480, lambda: process.kill() if process.poll() is None else None);timeout.start()
        try:
            for line in process.stdout:
                try:event=json.loads(line)
                except json.JSONDecodeError:continue
                with LOCK:
                    job=JOBS[job_id]
                    if event.get('type')=='progress':
                        job['events'].append(event)
                    elif event.get('type')=='result':
                        if hasattr(access, 'save_chart'):
                            directory=runtime_path('reports','charts').resolve()
                            for artifact in event['result'].get('artifacts',[]):
                                path=Path(artifact['path']).resolve()
                                if path.parent != directory:raise ValueError('Invalid chart path.')
                                access.save_chart(JOB_OWNERS[job_id],path.name,path.read_text(encoding='utf-8'))
                        job.update(status='complete',result=event['result'])
                    elif event.get('type')=='error':job.update(status='error',message=event['message'],review=event.get('review'))
            process.wait()
        finally:timeout.cancel()
        with LOCK:
            if JOBS[job_id]['status']=='running':
                JOBS[job_id].update(status='error',message='The investigation stopped before returning an answer. It has not been retried automatically.')
    except Exception:
        if process and process.poll() is None:process.kill()
        with LOCK:JOBS[job_id].update(status='error',message='The investigation could not finish or save its chart. No automatic retry was made.')
    finally:
        with LOCK:PROCESSES.pop(job_id,None)


# Import the web framework only in the server, not in analytical workers.
def create_app(settings=None, access=None):
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route

    settings = settings or WebSettings()
    access = access or create_access_store(runtime_path('state', 'web_access.sqlite3'))

    def reply(status, message):
        return JSONResponse({'message': message}, status_code=status)

    def owner(request):
        if not settings.auth_required:
            return 'local-owner'
        return access.owner(request.cookies.get('causyn_session'))

    def prune():
        cutoff = time.time() - 86400
        for job_id in list(JOBS):
            if JOBS[job_id]['status'] != 'running' and JOB_CREATED.get(job_id, 0) < cutoff:
                JOBS.pop(job_id, None); JOB_OWNERS.pop(job_id, None); JOB_CREATED.pop(job_id, None)
        # Charts are temporary. Only session-owned, retained jobs can download them.
        directory = runtime_path('reports', 'charts')
        if directory.is_dir() and runtime_path() != ROOT:
            for path in directory.glob('*.html'):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError:
                    pass

    async def body(request):
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            raise ValueError('Send JSON.')
        chunks, length = [], 0
        async for chunk in request.stream():
            length += len(chunk)
            if length > 12000:
                raise ValueError('Request is too large.')
            chunks.append(chunk)
        try:
            payload = json.loads(b''.join(chunks))
        except (ValueError, UnicodeDecodeError):
            raise ValueError('Send a valid JSON object.') from None
        if not isinstance(payload, dict):
            raise ValueError('Send a JSON object.')
        return payload

    async def health(request):
        # Liveness only: makes no database or Gemini requests.
        return JSONResponse({'status': 'ok'})

    async def config(request):
        return JSONResponse({'presets': PRESETS, 'local_only': not settings.production,
                             'live_enabled': settings.live, 'auth_required': settings.auth_required and not settings.public_live,
                             'public_live': settings.public_live, 'guides': GUIDES,
                             'limits': {'daily':settings.daily_limit,'hourly_session':settings.session_limit},
                             'authenticated': bool(owner(request))})

    async def public_session(request):
        # Only mint on a user-initiated Live request, never on a public page view.
        if not settings.public_live or not settings.live:
            return reply(403, 'Public Live is unavailable. Recorded examples remain available.')
        try:
            payload = await body(request)
            if payload:
                raise ValueError('Public session requests need an empty JSON object.')
        except ValueError as error:
            return reply(400, str(error))
        if owner(request):
            return JSONResponse({'authenticated': True})
        if not access.login_allowed(limit=60):
            return reply(429, 'Too many new Live sessions. Try a recorded example or return in 15 minutes.')
        token = access.new_session()
        response = JSONResponse({'authenticated': True})
        response.set_cookie('causyn_session', token, max_age=21600, httponly=True,
                            secure=settings.secure_cookie, samesite='strict', path='/')
        return response

    async def login(request):
        if not access.login_allowed():
            return reply(429, 'Too many sign-in attempts. Wait 15 minutes.')
        try:
            payload = await body(request)
        except ValueError as error:
            return reply(400, str(error))
        code = payload.get('access_code')
        if (not isinstance(code, str) or not settings.access_code or
                not hmac.compare_digest(code.encode(), settings.access_code.encode())):
            return reply(401, 'The access code is incorrect.')
        # Revoke any old cookie before issuing another session.
        access.logout(request.cookies.get('causyn_session'))
        token = access.new_session()
        response = JSONResponse({'authenticated': True})
        response.set_cookie('causyn_session', token, max_age=21600, httponly=True,
                            secure=settings.secure_cookie, samesite='strict', path='/')
        return response

    async def logout(request):
        access.logout(request.cookies.get('causyn_session'))
        response = JSONResponse({'authenticated': False})
        response.delete_cookie('causyn_session', path='/', secure=settings.secure_cookie,
                               httponly=True, samesite='strict')
        return response

    async def investigate(request):
        try:
            payload = await body(request)
            if 'guided' in payload:
                if payload.get('mode') != 'live':
                    raise ValueError('Guided date selections require Live. Recorded examples have fixed dates.')
                payload['question'] = guided_question(payload['guided'])
            question = payload.get('question')
            if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1200:
                raise ValueError('Enter a question of 1–1,200 characters.')
            mode = payload.get('mode')
            if mode not in ('demo', 'live'):
                raise ValueError('Choose Demo or Live.')
        except ValueError as error:
            return reply(400, str(error))
        session = owner(request)
        if mode == 'demo':
            selected = payload.get('demo_id')
            if (not isinstance(selected, str) or selected not in PRESETS or
                    question.strip() != PRESETS[selected]['question']):
                return reply(400, 'Demo supports recorded examples only. Choose an example or switch to Live.')
        else:
            if not settings.live:
                return reply(403, 'Live analysis is disabled on this deployment. Explore a recorded example.')
            if not session:
                return reply(401, 'Start a Live browser session to investigate.' if settings.public_live else 'Sign in to use Live analysis.')
        with LOCK:
            prune()
            if mode == 'live' and any(j['status'] == 'running' and j['mode'] == 'live' for j in JOBS.values()):
                return reply(409, 'An investigation is already running. Wait for it to finish.')
            if mode == 'live' and not access.admit(session, settings.daily_limit, settings.session_limit):
                return reply(429, 'The hourly or daily Live investigation limit has been reached. Demo remains available.')
            # Public examples return synchronously, with no persistent job allocation.
            if mode == 'demo':
                return JSONResponse({'result': demo_result(payload['demo_id'])})
            while len(JOBS) >= 20:
                completed = next((key for key, job in JOBS.items() if job['status'] != 'running'), None)
                if completed is None:
                    return reply(409, 'The investigation workspace is busy.')
                JOBS.pop(completed); JOB_OWNERS.pop(completed, None); JOB_CREATED.pop(completed, None)
            job_id = uuid.uuid4().hex
            JOBS[job_id] = {'id': job_id, 'status': 'running', 'events': [],
                            'question': question.strip(), 'mode': mode}
            JOB_OWNERS[job_id] = session
            JOB_CREATED[job_id] = time.time()
        threading.Thread(target=run_job, args=(job_id, payload, access), daemon=True).start()
        return JSONResponse({'id': job_id}, status_code=202)

    async def job(request):
        session = owner(request)
        if not session:
            return reply(401, 'Sign in to view this investigation.')
        job_id = request.path_params['job_id']
        with LOCK:
            prune()
            snapshot = dict(JOBS[job_id]) if JOB_OWNERS.get(job_id) == session and job_id in JOBS else None
        return JSONResponse(snapshot) if snapshot else reply(404, 'Investigation not found. It may have expired or the server restarted.')

    async def chart(request):
        session = owner(request)
        if not session:
            return reply(401, 'Sign in to open this chart.')
        name = request.path_params['name']
        if not re.fullmatch(r'[a-zA-Z0-9_-]+\.html', name):
            return reply(404, 'Chart not found.')
        if hasattr(access, 'get_chart'):
            content=access.get_chart(session,name)
            if content is not None:
                return Response(content,media_type='text/html',headers={
                    'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"})
        with LOCK:
            prune()
            permitted = any(
                JOB_OWNERS.get(key) == session and item['status'] == 'complete' and
                any(Path(artifact.get('path', '')).name == name for artifact in item.get('result', {}).get('artifacts', []))
                for key, item in JOBS.items())
        directory = runtime_path('reports', 'charts').resolve()
        path = (directory / name).resolve()
        if not permitted or path.parent != directory or not path.is_file():
            return reply(404, 'Chart not found. It may have expired.')
        return Response(path.read_bytes(), media_type='text/html', headers={
            'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"})

    async def asset(request):
        names = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        name = names[request.url.path]
        media = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'}[name.rsplit('.', 1)[-1]]
        return Response((UI / name).read_bytes(), media_type=media)

    @asynccontextmanager
    async def lifespan(app):
        yield
        # This app deliberately uses one process and one instance: jobs are in memory.
        with LOCK:
            for process in PROCESSES.values():
                if process.poll() is None:
                    process.kill()
            active = list(PROCESSES.values())
        for process in active:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    app = Starlette(debug=False, lifespan=lifespan, routes=[
        Route('/healthz', health), Route('/api/config', config),
        Route('/api/login', login, methods=['POST']), Route('/api/logout', logout, methods=['POST']),
        Route('/api/session', public_session, methods=['POST']),
        Route('/api/investigate', investigate, methods=['POST']),
        Route('/api/jobs/{job_id}', job), Route('/api/charts/{name}', chart),
        Route('/', asset), Route('/app.js', asset), Route('/style.css', asset)])

    async def safeguards(request, call_next):
        if request.url.path != '/healthz' and request.headers.get('host') not in settings.hosts:
            response = reply(403, 'This host is not permitted.')
        elif request.method not in ('GET', 'HEAD', 'POST'):
            response = reply(405, 'Method not permitted.')
        elif request.method == 'POST' and request.headers.get('origin') not in settings.origins:
            response = reply(403, 'Request origin not permitted.')
        else:
            response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if settings.production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if 'Content-Security-Policy' not in response.headers:
            response.headers['Content-Security-Policy'] = ("default-src 'self'; script-src 'self'; "
                "style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; connect-src 'self'; form-action 'self'")
        return response
    from starlette.middleware.base import BaseHTTPMiddleware
    app.add_middleware(BaseHTTPMiddleware, dispatch=safeguards)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.worker:
        worker()
    else:
        if args.port is not None:
            os.environ['PORT'] = str(args.port)
        settings = WebSettings()
        import uvicorn
        print(f'CAUSYN is ready: {settings.origin}', flush=True)
        print('Demo is recorded. Live is limited and uses private browser sessions.', flush=True)
        uvicorn.run(create_app(settings), host=settings.bind, port=settings.port, workers=1,
                    proxy_headers=False, access_log=False, server_header=False,
                    limit_concurrency=100, timeout_keep_alive=5, timeout_graceful_shutdown=15)
