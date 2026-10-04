import psycopg

with psycopg.connect(
    host="localhost",
    port=5432,
    dbname="causyn",
    user="aman",
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database();")
        print(f"Connected successfully to: {cursor.fetchone()[0]}")
        