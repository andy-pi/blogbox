from app import app, db
from app.models import BlogBoxUser

puser = BlogBoxUser("admin@blogbox.com", "password", "test.blogbox.com", "admin","blogbox1")
			
db.session.add(puser)
db.session.commit()
