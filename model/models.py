from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    points = db.Column(db.Integer, nullable=False)
    nickname = db.Column(db.String, nullable=False)
