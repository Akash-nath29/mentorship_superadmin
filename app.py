from urls import app
# from model import db
import os

# db.init_app(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
