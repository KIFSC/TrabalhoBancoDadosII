from flask import Flask

app = Flask(__name__)
app.secret_key = "chave_secreta_pepgh_humana"

from views import *

if __name__ == "__main__":
    app.run(debug=True)