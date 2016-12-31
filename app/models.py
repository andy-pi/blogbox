from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class BlogBoxUser(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  email = db.Column('email', db.String(128), unique=True)
  password = db.Column('password', db.String(256))
  registered_on = db.Column('registered_on' , db.DateTime)
  pauthor = db.Column('pauthor', db.String(128)) 
  psitename = db.Column('psitename', db.String(128))
  psiteurl = db.Column('psiteurl', db.String(256), unique=True) 
  ptimezone = db.Column('ptimezone', db.String(64))
  role= db.Column('role', db.String(32)) 
  pdefault_pagination = db.Column('pdefault_pagination', db.Integer)
  plinks = db.Column('plinks', db.Text)
  psocial = db.Column('psocial', db.Text) 
  pdisqus_sitename = db.Column('pdisqus_sitename', db.String(128))
  ptheme = db.Column('ptheme', db.String(128))
  ppaid = db.Column('ppaid', db.Boolean) 
  paws_profile = db.Column('paws_profile', db.String(64))
  db_app_token = db.Column('db_app_token', db.String(128))
  db_userid = db.Column('db_userid', db.String(256))
  pdebug = db.Column('pdebug', db.Text) 
  pmenu = db.Column('pmenu', db.Text)
  psubtitle = db.Column('psubtitle', db.String(128))
  psitelogo = db.Column('psitelogo', db.String(256))
  pfavicon = db.Column('pfavicon', db.String(256))
  pbanner = db.Column('pbanner', db.String(256))
  ptime_since_site_change= db.Column('ptime_since_site_change' , db.DateTime)
  
    
  def __init__(self, email, password, psiteurl, role, paws_profile):
		# PASSED FROM REGISTRATION FORM TO SET
		self.email = email
		self.set_password(password)
		self.psiteurl=psiteurl
		self.role=role
		self.paws_profile=paws_profile
		
		# SELF SET
		self.ppaid = False 		# set to false for new signups
		self.registered_on = datetime.utcnow()
		self.pdefault_pagination = 10
		self.plinks = "AndyPi,http://andypi.co.uk"
		self.psocial = "twitter,https://twitter.com/andypi_tech\ngithub,https://github.com/andy-pi"
		self.pmenu = "Blogbox,https://blogbox.com"
		self.ptheme = "tuxlite_tbs"
		self.pauthor = ""
		self.psitename = ""
		self.pdisqus_sitename = ""
		self.ptimezone = "Europe/London"
		self.db_app_token = ""
		psitelogo = "https://blogbox.com/static/blogbox_logo4.png"
		pfavicon = "https://blogbox.com/static/favicon.ico"
		pbanner = ""
		
  def is_authenticated(self):
        return True
 
  def is_active(self):
        return True
 
  def is_anonymous(self):
        return False
 
  def get_id(self):
        return unicode(self.id)
		
  def set_password(self, password):
        self.password = generate_password_hash(password)

  def check_password(self, password):
        return check_password_hash(self.password, password)