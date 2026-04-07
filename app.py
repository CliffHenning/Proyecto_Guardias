from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/guardias")
def vista_guardias():
    return render_template("guardias.html")

@app.route("/presencia")
def vista_presencia():
    return render_template("presencia.html")

if __name__ == "__main__":
    app.run(debug=True)