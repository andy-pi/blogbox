import sys, os
PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PATH)

from app import app

from werkzeug.debug import DebuggedApplication
app.wsgi_app = DebuggedApplication(app.wsgi_app, True)

if __name__ == "__main__":
    app.run()
	
	
	
