import sqlite3
from flask import Flask, jsonify, g, request

DATABASE = "movies.db"

app = Flask(__name__)

@app.get("/")
def hello():
    return jsonify({"message": "Movies API"})

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()
        
@app.get("/movies")
def list_movies():
    db = get_db()
    cursor = db.execute(
        "SELECT id, title, year, rating, director_id FROM movies"
    )
    rows = cursor.fetchall()

    movies = [dict(row) for row in rows]

    return jsonify(movies)

@app.get("/movies/<int:movie_id>")
def get_movie(movie_id):
    db = get_db()
    cursor = db.execute(
        "SELECT id, title, year, rating, director_id FROM movies WHERE id = ?",
        (movie_id,),
    )
    row = cursor.fetchone()

    if row is None:
        return jsonify({"error": "Movie not found"}), 404

    return jsonify(dict(row))

@app.get("/movies/<int:movie_id>/full")
def get_movie_full(movie_id):
    db = get_db()
    cursor = db.execute(
        """
        SELECT
          movies.id AS movie_id,
          movies.title,
          movies.year,
          movies.rating,
          directors.id AS director_id,
          directors.name AS director_name,
          directors.country AS director_country
        FROM movies
        INNER JOIN directors ON movies.director_id = directors.id
        WHERE movies.id = ?
        """,
        (movie_id,),
    )
    row = cursor.fetchone()

    if row is None:
        return jsonify({"error": "Movie not found"}), 404

    return jsonify(dict(row))

@app.post("/movies")
def create_movie():
    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    if "title" not in data:
        return jsonify({"error": "title is required"}), 400

    if "director_id" not in data:
        return jsonify({"error": "director_id is required"}), 400

    db = get_db()
    
    try: 

        cursor = db.execute(
            """
            INSERT INTO movies (title, year, director_id)
            VALUES (?, ?, ?)
            """,
            (data["title"], data["year"], data["director_id"]),
        )
        db.commit()

    except sqlite3.IntegrityError:
        return jsonify({"error": "Movies conflict with existing data or director_id is invalid"}), 409

    return (
        jsonify(
            {
                "id": cursor.lastrowid,
                "title": data["title"],
                "year": data["year"],  
                "director_id": data["director_id"],
            }
        ),
        201,
    )

@app.delete("/movies/<int:movie_id>")
def delete_movie(movie_id):

    db = get_db()

    cursor = db.execute(
        "DELETE FROM movies WHERE id = ?",
        (movie_id,),
    )

    db.commit()

    if cursor.rowcount == 0:
        return jsonify(
            {"error": "Movie not found"}
        ), 404

    return "", 204    

@app.patch("/movies/<int:movie_id>")
def update_movie(movie_id):

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify(
            {"error": "Request body must be a JSON object"}
        ), 400

    updates = []
    values = []

    if "title" in data:
        updates.append("title = ?")
        values.append(data["title"])

    if "director_id" in data:
        updates.append("director_id = ?")
        values.append(data["director_id"])

    if not updates:
        return jsonify(
            {"error": "No updatable fields provided"}
        ), 400

    values.append(movie_id)

    set_clause = ", ".join(updates)

    sql = (
        "UPDATE movies "
        "SET " + set_clause +
        " WHERE id = ?"
    )

    db = get_db()

    try:
        cursor = db.execute(sql, values)
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({
            "error": "Update conflicts with existing data or director_id is invalid."
        }), 409

    if cursor.rowcount == 0:
        return jsonify(
            {"error": "Movie not found"}
        ), 404

    row = db.execute(
        """
        SELECT id, title, year, rating, director_id
        FROM movies
        WHERE id = ?
        """,
        (movie_id,),
    ).fetchone()

    return jsonify(dict(row)), 200

@app.get("/directors/<int:director_id>/movies")
def get_director_with_movies(director_id):
    db = get_db()

    cursor = db.execute("""
        SELECT
            d.id   AS director_id,
            d.name AS director_name,
            m.id   AS movie_id,
            m.title,
            m.year,
            m.rating
        FROM directors d
        LEFT JOIN movies m
            ON d.id = m.director_id
        WHERE d.id = ?
    """, (director_id,))

    rows = cursor.fetchall()

    # No rows means the director doesn't exist
    if not rows:
        return jsonify({"error": "Director not found"}), 404

    director = {
        "id": rows[0]["director_id"],
        "name": rows[0]["director_name"],
        "movies": []
    }

    for row in rows:
        if row["movie_id"] is not None:
            director["movies"].append({
                "id": row["movie_id"],
                "title": row["title"],
                "year": row["year"],
                "rating": row["rating"]
            })

    return jsonify(director), 200

if __name__ == "__main__":
    app.run(debug=True)