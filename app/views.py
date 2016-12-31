from flask import Flask,session, request, flash, url_for, redirect, render_template, abort ,g
from flask.ext.login import LoginManager, login_user , logout_user , current_user , login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db, celery
from celery.task.control import inspect
from app.models import BlogBoxUser
from functools import wraps
from sqlalchemy.sql import exists
import os, shutil, dropbox, subprocess, pytz, csv, re, hmac, json
from dropbox.client import DropboxOAuth2Flow
from flask.ext.mail import Mail, Message
import boto3,botocore
from boto3.session import Session as botosession
from cloudflare import CloudFlare as cf # not a pip module - on local machine?? CloudFlare
from itsdangerous import URLSafeTimedSerializer
from hashlib import sha256
import time, datetime

# see requirements.txt for python modules

############# SETUP GLOBAL VARIABLES ############

THEMESLIST=['aboutwilson', 'nikhil-theme', 'tuxlite_tbs', 'tuxlite_zf', 'franticworld', 'bootstrap2-dark', 'new-bootstrap2', 'Flex', 'nmnlist', 'simple-bootstrap']
NEWTHEMES=['blue-penguin', 'lovers', 'relapse', 'pelican-bootstrap3', 'octopress', 'voidy-bootstrap',]
MISS=['bootstrap2', 'martin-pelican', ]

CREATE_NEW_BUCKET_PROFILE="blogbox1" # MUST BE SAVED in /root/.aws/credentials on pi
APP_ADMIN_EMAIL='andy@blogbox.com'

HOMEDIR='/home/andy/apps/blogbox/'
ERRORDOC=os.path.join(HOMEDIR,"app/error.html")
PELICANCONF_FILENAME=os.path.join(HOMEDIR, "app/pelicanconf.py") # master copy in same directory as app
USER_DIR=os.path.join(HOMEDIR, "userdata")
AWSCMD=os.path.join(HOMEDIR, "env/bin/aws")
PELICAN_CMD=os.path.join(HOMEDIR,"env/bin/pelican")

ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])

roles=["trial", "user", "premium", "admin"]
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index' # redirect users to the login view if needed

mail = Mail(app)

############# FUNCTIONS ############

def required_roles(*roles):
	'''
	Required Roles is a simple function to allow mutiple user roles  (see http://flask.pocoo.org/snippets/98/). Flask-principle was found to be
	too complex for this project
	'''
	def wrapper(f):
		@wraps(f)
		def wrapped(*args, **kwargs):
			if get_current_user_role() not in roles:
			# archived users not in this list, therefore cannot login
				flash('Authentication error, please check your details and try again','error')
				return redirect(url_for('index'))
			return f(*args, **kwargs)
		return wrapped
	return wrapper

def get_current_user_role():
	return g.user.role

@login_manager.user_loader
def load_user(id):
    return BlogBoxUser.query.get(int(id)) # stored as unicode string, so need to convert to int before querying DB

@app.before_request
def before_request():
    g.user = current_user
	
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))
	
def parse_links(rawlinks):
	'''
	parse_links takes a csv / link break string as its input
	it returns a string with correct brackets to be understood 
	by pelican's conf file.
	'''
	try:
		csvlinks = csv.reader(rawlinks.split('\n'), delimiter=',')
		returned_links ="["
		for row in csvlinks:
			returned_links+="('"
			returned_links+=row[0]
			returned_links+="', '"
			returned_links+=row[1]
			returned_links+="')"
			returned_links+=","
		returned_links=returned_links[:-1] # remove last comma, a bit hackish
		returned_links+="]"
	except:
		returned_links=None
	return returned_links

def bucket_create(psiteurl):
	'''
	bucket_create creates a new bucket in the default profile, else returns and error
	NEEDS VALIDATION ON NEW NAME!!!!!!!!!!!!!!!!
	'''
	# get create new from config file MUST BE SAVE in /root/.aws/credentials
	mys3 = botosession(profile_name=CREATE_NEW_BUCKET_PROFILE)
	s3 = mys3.resource('s3')
	exists = True
	try:
		s3.create_bucket(Bucket=psiteurl, CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
		# https://github.com/boto/boto3/issues/125 for why this code above
		S3_REMOTE_PATH = "s3://" + str(psiteurl)
		p=subprocess.Popen([AWSCMD, "s3", "website", S3_REMOTE_PATH, "--index-document", "index.html", "--error-document", "error.html", "--profile", CREATE_NEW_BUCKET_PROFILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		out, err = p.communicate() # need to make an error handler
		
		p=subprocess.Popen([AWSCMD, "s3", "cp", ERRORDOC, S3_REMOTE_PATH, "--acl", "public-read", "--profile", CREATE_NEW_BUCKET_PROFILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		out, err = p.communicate() # need to make an error handler
				
		if psiteurl.endswith(".blogbox.com"):
			# cloudflare api add CNAME
			cname_rec=psiteurl + ".s3-website-eu-west-1.amazonaws.com"
			subdomain=psiteurl[:-13]
			cfapi = cf(app.config['CLOUDFLARE_EMAIL'], app.config['CLOUDFLARE_APIKEY'])
			cfresultNEW = cfapi.rec_new("blogbox.com", "CNAME", subdomain, cname_rec)
			dns_rec_id = cfapi.get_rec_id_by_name("blogbox.com",subdomain)
			cfresultEDIT = cfapi.rec_edit("blogbox.com", "CNAME", dns_rec_id, subdomain, cname_rec, service_mode=1, ttl=1)
			exists = True
		
	except botocore.exceptions.ClientError as e:
		#maybe send the errorcode via email??????
		#error_code = e.response['Error']['Code']
		#print e.response
		#if (error_code=="BucketAlreadyExists" or error_code=="IllegalLocationConstraintException"):
		exists = False
	return exists

	
def bucket_delete(psiteurl,paws_profile):
	'''
	bucket_delete deletes the specified bucket/siteurl, using the users corresponding aws_profile
	this utilises the AWS cli: aws s3 rb s3://bucket-name --force 
	'''
	S3_REMOTE_PATH = "s3://" + str(psiteurl)
	PROFILE_NAME = str(paws_profile)
	p=subprocess.Popen([AWSCMD, "s3", "rb", S3_REMOTE_PATH, "--region", "eu-west-1", "--force", "--profile", PROFILE_NAME ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = p.communicate()
	if psiteurl.endswith(".blogbox.com"):
		# cloudflare api remove CNAME
		subdomain=psiteurl[:-13]
		cfapi = cf(app.config['CLOUDFLARE_EMAIL'], app.config['CLOUDFLARE_APIKEY'])
		dns_rec_id = cfapi.get_rec_id_by_name("blogbox.com",subdomain)
		cfresultDEL = cfapi.rec_delete("blogbox.com", dns_rec_id)
		#print cfresultDEL
	else:
		pass
	
	return out, err

def save_pelicanconf(id):
	'''
	save_pelicanconf creates a copy of a standard pelican configuration file
	and appends user specific options to it which are saved in the database
	LOCATION SHOULD BE IN SUB FOLDER
	'''
	puser=BlogBoxUser.query.get(id)
	userpeliconf = os.path.join(USER_DIR, str(puser.id), "pelicanconf.py")
	userdir = os.path.dirname(userpeliconf)
	if not os.path.exists(userdir):
		os.makedirs(userdir)
	shutil.copyfile(PELICANCONF_FILENAME, userpeliconf)
	# append the following lines
	with open(userpeliconf, 'a') as the_file:
		the_file.write('AUTHOR = "' + puser.pauthor + '"\n') # 
		the_file.write('SITENAME = "' + puser.psitename  + '"\n')
		the_file.write('SITETITLE = SITENAME\n')
		the_file.write("TIMEZONE = '"+puser.ptimezone+"'\n")
		the_file.write("DEFAULT_PAGINATION = " + str(puser.pdefault_pagination) + "\n")
		parsed_links=parse_links(puser.plinks)
		if (parsed_links != None):
			the_file.write("LINKS = " +parsed_links + "\n")
		parsed_social=parse_links(puser.psocial)
		if (parsed_social != None):
			the_file.write("SOCIAL = " +parsed_social + "\n") 
		parsed_menu=parse_links(puser.pmenu)
		if (parsed_menu != None):
			the_file.write("MENUITEMS = " +parsed_menu + "\n") 
		#(('Archives', '/archives.html'), ('Categories', '/categories.html'), ('Tags', '/tags.html')) 
		the_file.write("DISQUS_SITENAME = '"+puser.pdisqus_sitename+"'\n") 
		the_file.write("THEME = '" + puser.ptheme + "'\n")
		if (puser.psubtitle !=None):
			the_file.write("SITESUBTITLE = '" + puser.psubtitle + "'\n")
		if (puser.psitelogo !=None):
			the_file.write("SITELOGO = '" + puser.psitelogo + "'\n")
		if (puser.pfavicon !=None):
			the_file.write("FAVICON = '" + puser.pfavicon + "'\n")
		if (puser.pbanner !=None):
			the_file.write("BANNER= '" + puser.pbanner + "'\n")
			


		
def dropbox_download(client, path, id, depth=0):
	'''
	dropbox_download gets all *.md files from "posts" and "pages" folders in the users
	blogbox folder in their Dropbox, preserving directory structure
	Only files < 10MB are downloaded.
	Based on http://blog.dwyer.co.za/2014/05/moving-files-from-dropbox-to-mega.html
	'''
	# get info from users dropbox
	folder_metadata = client.metadata(path) 
	contents = folder_metadata.get("contents")
	# for each item in the metadata
	for item in contents:
		if item.get("is_dir"): 
			dirname = item.get("path")[1:] # remove leading slash
			if depth==0: # if its the first depth only look for these two named folders
			# get only these directories
				if dirname[-5:] == "posts" or dirname[-5:] == "pages":
					# save to local disk under id=userid and dropbox directory
					localdirname=os.path.join(USER_DIR, str(id), 'dropbox', dirname)
					if not os.path.exists(localdirname):
						os.makedirs(localdirname)
					dropbox_download(client, item.get("path"), id, depth+1)
	
			else: # depth NOT 0 -any other run through can be any folder
			# add user id and dropbox to filepath
				localdirname=os.path.join(USER_DIR, str(id), 'dropbox', dirname)
				if not os.path.exists(localdirname):
					os.makedirs(localdirname)
				dropbox_download(client, item.get("path"), id, depth+1)

		else: #if not dir: get file extension and size
			fpath = item.get("path")
			exten = fpath.split(".")[-1]
			fsize = item.get("bytes")
			#only get files < 0.5mb and with .md extensions
			if fsize<500000 and (exten.lower()=="md"): 
				f = client.get_file(fpath)
				# add in the user id and dropbox to the filepath
				localfile = os.path.join(USER_DIR, str(id), 'dropbox', fpath.strip("/"))
				with open(localfile, 'wb') as out:
					out.write(f.read())
			else:
				# skip files with other extensions
				pass

def dropbox_upload_example(id):
	'''
	dropbox_upload_example uploads the blogbox post and pages
	folders along with the example post and pages to a users dropbox/apps/blogbox folder
	updated to include sitename in path
	'''
	puser = BlogBoxUser.query.get(id)
	client = dropbox.client.DropboxClient(str(puser.db_app_token))
	if (puser.db_app_token is not None):
		A1=os.path.join(HOMEDIR,'app/example/posts/example-post.md')
		A2=os.path.join(HOMEDIR,'app/example/pages/example-page.md')
		A3=os.path.join(HOMEDIR,'posts/example-post.md')
		A4=os.path.join(HOMEDIR,'pages/example-page.md')
		f1 = open(A1, 'rb')
		f2 = open(A2, 'rb')
		post_filename= '/' + str(puser.psiteurl) + A3
		page_filename= '/' + str(puser.psiteurl) + A4
		response1 = client.put_file(post_filename, f1)
		response2 = client.put_file(page_filename, f2)
		puser.pdebug=str(response1) + "/n /n" + str (response2)
		db.session.commit()
	
@celery.task				
def autopublish(id):
	'''
	publish is the heart of the BlogBox web app. It does the following things
	1. Gets users markdown files from dropbox	
	2. Runs pelican on the downloaded file
	3. Uploads the generated pelican blog to s3 using AWS cli (better than python boto)
		(http://docs.aws.amazon.com/cli/latest/reference/s3/cp.html)
	4. Deletes this users pelican output / db input to avoid conflicts on the next run
	5. Saves debug messages
	'''
	with app.app_context():
	
			puser = BlogBoxUser.query.get(id)
			dbfolder=os.path.join(USER_DIR, str(puser.id), 'dropbox', str(puser.psiteurl))
			PELIFOLDER=os.path.join(USER_DIR, str(puser.id), 'pelioutput')
			
			# 1. Get users markdown files from dropbox	
			try:
				client = dropbox.client.DropboxClient(str(puser.db_app_token))
				start_dir = "/" + str(puser.psiteurl) + "/"
				dropbox_download(client, start_dir, puser.id)
			except: 
				puser.pdebug = 'Dropbox error: - Account not authorised or no files in blogbox folder\n'
				db.session.commit()			
	
			# 2. Run pelican on the downloaded files, all options are specified by options file
			userpeliconf = os.path.join(USER_DIR, str(puser.id), "pelicanconf.py")
			save_pelicanconf(puser.id)
			try:
				# collects pelican command output to send to user
				p=subprocess.Popen([PELICAN_CMD, dbfolder, "-s", userpeliconf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				pout, perr = p.communicate()
				debugtext = '<p>Pelican output:<br>'
				debugtext += pout
				debugtext += '</p>Pelican error:<br>' 
				debugtext += perr
				
			except: 
				if os.path.exists(dbfolder):
					shutil.rmtree(dbfolder) # delete downloaded files
				debugtext += '</p>Pelican error:<br>'
				debugtext += perr
				puser.pdebug = debugtext
				db.session.commit()
		
			# 3. upload to s3
			S3_REMOTE_PATH = "s3://" + str(puser.psiteurl) #+ ".s3-website-eu-west-1.amazonaws.com"
			PROFILE_NAME = str(puser.paws_profile)
			try:
				p=subprocess.Popen([AWSCMD, "s3", "sync", PELIFOLDER, S3_REMOTE_PATH, "--delete", "--acl", "public-read", "--profile", PROFILE_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				sout, serr = p.communicate()
				p2=subprocess.Popen([AWSCMD, "s3", "cp", ERRORDOC, S3_REMOTE_PATH, "--acl", "public-read", "--profile", CREATE_NEW_BUCKET_PROFILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				debugtext += '</p>S3 Upload details:<br>'
				debugtext += sout
				debugtext += '</p>S3 Upload errors:<br>'
				debugtext += serr
				puser.pdebug = debugtext
				db.session.commit()
	
			except:
				debugtext += '</p>S3 Upload details:<br>'
				debugtext += sout
				debugtext += '</p>S3 Upload errors:<br>'
				debugtext += serr
				puser.pdebug = debugtext
				db.session.commit()
		
			# 4. Deletes this users pelican output and dropbox download to avoid conflicts on the next run
			if os.path.exists(PELIFOLDER):
				shutil.rmtree(PELIFOLDER) #delete pelican output
			if os.path.exists(dbfolder):
				shutil.rmtree(dbfolder) 


@celery.task				
def queue_email(msgsender,msgrecipient,msgsubject,msghtml):
	msg = Message(msgsubject, sender=msgsender, recipients=[msgrecipient])
	msg.html= msghtml
	mail.send(msg)

############# HTTP FUNCTIONS - ADMIN ONLY ################

@app.route('/user_admin' )
@required_roles('admin')
@login_required
def user_admin():
	'''
	list of users and option to delete for admin only
	'''
	puser = BlogBoxUser.query.all()    
	return render_template('user_admin.html', puser=puser)	

@app.route('/user_delete/<id>' , methods=['POST', 'GET'])
@required_roles('admin')
@login_required
def user_delete (id):
	'''
	user_delete completely deletes the user of chosen id including:
	1. Removing the user's folder
	2. Deleting the s3 bucket and all contents (including removing the DNS records for any *.blogbox.com sites)
	3. Sending the user and account closed confirmation email 
	4. Removing the user from the database
	'''
	puser = BlogBoxUser.query.get(id)
	# 1. remove users folder
	if os.path.exists(os.path.join(USER_DIR, puser.psiteurl)):
		shutil.rmtree(os.path.join(USER_DIR, puser.psiteurl))
		
	# 2. Remove s3 bucket/cloudflare; 
	try:
		out, err = bucket_delete(puser.psiteurl,puser.paws_profile)
	except:
		flash ('Error removing bucket')

	# 3. Send account deleted confirmation email to user
	message_html = "Dear " + puser.email + ",</p><p>Your Site: " + puser.psiteurl + " has been removed.</p><p>We're sorry to see you go - thanks for using BlogBox. To complete your account closure, please go to <a href='https://www.dropbox.com/account#security'>Your Dropbox Account - Security</a> and unlink the BlogBox app. You will not receive any further communication from us.</p><p>If you wish to sign up for a new account, please go to <a href='http://blogbox.com'>http://blogbox.com</a></p><p>Best Regards,</p><p><a href='mailto:andy@blogbox.com'>Andy, BlogBox Developer</a></p>"
	task=queue_email.apply_async(args=[APP_ADMIN_EMAIL,puser.email,'BlogBox Account Closure',message_html])
		
	# 4. Remove from database (will this crash the queued task if its already been deleted?)
	try:
		db.session.delete(puser)
		db.session.commit()
		flash ('User deleted')
	except:
		flash ('Error removing user account from the database')
		
	return redirect(url_for('user_admin'))

@app.route('/user_activate/<id>' , methods=['POST', 'GET'])
@required_roles('admin')
@login_required
def user_activate (id):
	'''
	check if bucket exists if so then just change ppaid=True
	use AWS cli to create bucket
	if last x of psiteurl is .blogbox.com, then add cloudflare api bit
	'''	
	puser = BlogBoxUser.query.get(id)
	save_pelicanconf(puser.id)
	puser.ppaid=True
	db.session.commit()
	flash('User account activated')
	return redirect(url_for('user_admin'))

@app.route('/user_deactivate/<id>' , methods=['POST', 'GET'])
@required_roles('admin')
@login_required
def user_deactivate (id):
	'''
	user_deactivate simply sets the user's paid flag to false
	this flag identifies the account is in a pending state
	such users are prevented from publishing their blog
	'''
	puser = BlogBoxUser.query.get(id)
	puser.ppaid=False
	db.session.commit()
	flash('User account deactivated')
	return redirect(url_for('user_admin'))


############# HTTP FUNCTIONS - USER ################

@app.route('/user_register' , methods=['GET','POST'])
def user_register():
	'''
	user_register allows a user to register for a BlogBox account.
	A bucket is created (if it is available) - note this will be orphaned if email is duplicated
	Their email, password and site url is added to the database
	The account is added in the pending state, and a notification email is sent to the administrator
	'''
	if request.method == 'GET':
		return render_template('user_register.html')
		
	else: # POST METHOD
		puser = BlogBoxUser(request.form['email'] , request.form['password'], request.form['psiteurl'],"user", CREATE_NEW_BUCKET_PROFILE)
		subdomain=puser.psiteurl[:-13]
		if (puser.psiteurl.endswith(".blogbox.com") and subdomain in app.config['BLOGBOX_BANNED_SUBDOMAINS']):
			flash('Error: This site url is already registered, please choose a different one.')
			return redirect(url_for('user_register'))
		
		else: # either not a blogbox subdomain or the blogbox subdomain is not banned
					
			test=db.session.query(exists().where(BlogBoxUser.email==puser.email)).scalar()
			# simply remove the 2nd condition here to allow anyone to register
			if (test == False): #and puser.email in app.config['REGISTERED_EMAILS'])
				bucket_exists=bucket_create(puser.psiteurl)
				if (bucket_exists==True):
					# first try to create bucket. If exists just returns it (and we check later that it is not in our db, as it is a unique token), if not, error
					# 1. Add to database
					puser.ptime_since_site_change = datetime.datetime.now()
					db.session.add(puser)
					db.session.commit()
					# 2. Send notification email to administrator
					senderemail=request.form['email']
					message_html = "<p>Dear BlogBox Admin,</p> A new user has registered with BlogBox.<p> Please log in and activate their account.</p>"
					task=queue_email.apply_async(args=[senderemail,APP_ADMIN_EMAIL,'BlogBox New User',message_html])
					flash('You are successfully registered with BlogBox! You can log in now, but your account can take upto 24 hours to be activated.')
					return redirect(url_for('index'))
					
				else: # couldn't create bucket
					flash('Error: This site url is already registered, please choose a different one.')
					return redirect(url_for('user_register'))
			else: # email already registered or not on approved list
				flash('Error: This email address is already registered or not approved')
				return redirect(url_for('user_register'))
	


@app.route('/user_pass_reset', methods=['GET','POST'])
def user_pass_reset():
	'''
	user_pass_reset shows a form to enter the email address and send a rest link to it
	'''
	if request.method == 'POST':
		emailtoreset=request.form['email']
		# check user with this password exists else error - NEED A BETTER ERROR OR NONE AT ALL
		user = BlogBoxUser.query.filter_by(email=emailtoreset).first_or_404()
		
		# Here we use the URLSafeTimedSerializer we created 
		token = ts.dumps(emailtoreset, salt='recover-key')
		recover_url = url_for('reset_with_token',token=token,_external=True)
		message_html= "<p>Dear BlogBox User,</p> You requested to change your password. Please click on the link below and enter a new password to reset it.</p>" + recover_url
		task=queue_email.apply_async(args=['andy@blogbox.com',emailtoreset,'Password reset requested',message_html])
		
		flash('Your password reset message is on its way to your inbox!')
		return redirect(url_for('index'))
	
	else: # GET method
		return render_template('user_pass_reset.html')
	
	
@app.route('/reset/<token>', methods=["GET", "POST"])
def reset_with_token(token):
	'''
	reset_with_token shows a form with a new password field
	'''
	try:
		resetemail = ts.loads(token, salt="recover-key", max_age=86400)
	except:
		abort(404)

	if request.method == 'POST': 
		newpassword=request.form['newpassword']
		resetuser = BlogBoxUser.query.filter_by(email=resetemail).first_or_404()
		
		resetuser.password = generate_password_hash(newpassword)
		db.session.commit()
		flash('Password updated successfully')
		return redirect(url_for('index'))
	
	return render_template('reset_with_token.html', token=token)

@app.route('/change_site', methods=['GET','POST'])
@login_required
def change_site():
	'''
	change_site changes the users s3 bucket name and DNS records (for *.blogbox.com)
	'''
	puser=g.user
	if request.method == 'POST': 
		current_date = datetime.datetime.now()
		if (puser.ptime_since_site_change==None or current_date>puser.ptime_since_site_change):
			newsiteurl=request.form['newsiteurl']
			bucket_exists=bucket_create(newsiteurl)
			if (bucket_exists==True):
				out, err = bucket_delete(puser.psiteurl,puser.paws_profile)
				# send out/err notification to admin, need to format this better
				message_html= str(out) + str(err)
				task=queue_email.apply_async(args=[puser.email,'andy@blogbox.com','Site Domain Changed Notification',message_html])
				# update database with new site name and datetime
				puser.ptime_since_site_change = datetime.datetime.now() + datetime.timedelta(days=1)
				puser.psiteurl=newsiteurl
				puser.paws_profile=CREATE_NEW_BUCKET_PROFILE
				db.session.add(puser)
				db.session.commit()
				output = dropbox_upload_example(puser.id)
				flash('Your domain name was succesfully changed! It may take a couple of hours for blogbox.com domain names changes to be fully accessible.')
				return redirect(url_for('settings'))
								
			else: # bucket creation error
				flash('Error: Your new site url is already registered, please choose a different one')
				return redirect(url_for('change_site'))
		else:
			flash('You can only change you site name every 24 hours')
			return redirect(url_for('change_site'))
				
	else: #GET method
		return render_template('change_site.html', puser=g.user)
	
			
@app.route('/', methods=['GET','POST'])
def index():
	'''
	index displays the home page of the BlogBox app.
	Users can log in using their email and password
	and be redirected to the settings page
	'''
	if request.method == 'GET':
		puser=g.user
		return render_template('index.html', puser=g.user)
	email = request.form['email']
	password = request.form['password']
	registered_user = BlogBoxUser.query.filter_by(email=email).first()
	if registered_user is None:
		flash('Email is invalid' , 'error')
		return redirect(url_for('index'))
	if not registered_user.check_password(password):
		flash('Password is invalid','error')
		return redirect(url_for('index'))
	login_user(registered_user)
	flash('Logged in successfully')
	return redirect(request.args.get('next') or url_for('settings'))
 
@app.route('/settings' , methods=['POST', 'GET'])
@login_required
def settings():
	'''
	settings is the main user page which allows pelican settings to be updated
	'''
	puser = g.user # Get current user
	if request.method == 'POST':
		#the request.form['XYZ'] is requesting the name"XYZ" of the input tag of html page
		puser.email = re.sub('[^a-zA-Z0-9-_@.]', '', request.form['email'])
		puser.pauthor = re.sub('[^a-zA-Z0-9-_@.#]', '', request.form['pauthor'])
		puser.psitename = re.sub('[^a-zA-Z0-9-_@.# ]', '', request.form['psitename'])
		puser.ptimezone = request.form['ptimezone']
		puser.pdefault_pagination = request.form['pdefault_pagination']
		puser.plinks = re.sub('[^a-zA-Z0-9-_@:/.,\n]', '', request.form['plinks'])
		puser.psocial = re.sub('[^a-zA-Z0-9-_@:/.,\n]', '', request.form['psocial'])
		puser.pdisqus_sitename = re.sub('[^a-zA-Z0-9-_@.]', '', request.form['pdisqus_sitename'])
		puser.ptheme = request.form['ptheme']
		puser.pmenu = re.sub('[^a-zA-Z0-9-_@:/.,\n]', '',request.form['pmenu'])
		puser.psubtitle = re.sub('[^a-zA-Z0-9-_@.# ]', '', request.form['psubtitle'])
		puser.psitelogo = re.sub('[^a-zA-Z0-9-_:./]', '', request.form['psitelogo'])
		puser.pfavicon = re.sub('[^a-zA-Z0-9-_:./]', '', request.form['pfavicon'])
		puser.pbanner = re.sub('[^a-zA-Z0-9-_:./]', '', request.form['pbanner'])
		
  		db.session.commit()
		save_pelicanconf(puser.id)
		flash('Settings saved successfully')
	
	domainend = puser.psiteurl[-13:]
	tzones = pytz.common_timezones
	return render_template('settings.html', puser=g.user, domainend=domainend,  themeslist=THEMESLIST, tzones=tzones)
 
@app.route('/view_themes', methods=['GET'])
def view_themes():
	return render_template('view_themes.html', themeslist=THEMESLIST)
 
@app.route('/publish', methods=['GET'])
@login_required
def publish():
	puser=g.user
	if (puser.ppaid): 
		current_milli_time = int(round(time.time() * 1000))
		taskid = "task-" + str(puser.id) + "-" + str(current_milli_time)
		task=autopublish.apply_async(args=[puser.id], task_id=taskid)
		'''
		i = inspect()
		cqueue = i.reserved()
		ctasklist = cqueue['celery@blogbox'] 
		if (ctasklist != []):
			for item in ctasklist: # for each task in the list
				info = item[0] 
				reservedtask=info['id'] # get task id
				teststring = "task-" + str(puser.id) # see if it contains
				flash (teststring)
				flash (reservedtask)
				if (teststring not in reservedtask):
					current_milli_time = int(round(time.time() * 1000))
					taskid = "task-" + str(puser.id) + "-" + str(current_milli_time)
					task=autopublish.apply_async(args=[puser.id], task_id=taskid)
				else:
					flash ("not added to queue")

		flash (taskid)
		flash (ctasklist)
		'''
		return redirect(url_for('settings'))
	else:
		flash ("Your subscription is not active!")
		puser.pdebug="Your subscription is not active!"
		db.session.commit()
		return redirect(url_for('settings'))

def get_dropbox_auth_flow():
	redirect_uri = "https://blogbox.com/dropbox-auth-finish"
	return DropboxOAuth2Flow(app.config['DB_APP_KEY'], app.config['DB_APP_SECRET'], redirect_uri, session, "dropbox-auth-csrf-token")
	
@app.route('/dropbox_auth_start', methods=['GET'])
@login_required
def dropbox_auth_start():
	authorize_url = get_dropbox_auth_flow().start()
	return redirect(authorize_url)
	
@app.route('/dropbox-auth-finish')
@login_required
def dropbox_auth_finish():
	puser=g.user
	try:
		access_token, uid, extras = get_dropbox_auth_flow().finish(request.args)
		puser.db_app_token = access_token
		puser.db_userid = uid #new
		db.session.commit()
		output = dropbox_upload_example(puser.id)
		flash('You have authorized your dropbox account to use BlogBox! Sync and check your Dropbox/Apps/Blogbox folder for example posts and pages')
		return redirect(url_for('settings'))
	except DropboxOAuth2Flow.BadRequestException, e:
		http_status(400)
	except DropboxOAuth2Flow.BadStateException, e:
		#Start the auth flow again.
		redirect_to("/dropbox-auth-start")
	except DropboxOAuth2Flow.CsrfException, e:
		http_status(403)
	except DropboxOAuth2Flow.NotApprovedException, e:
		flash('You declined to approve Blogbox, it cannot work without access to your Dropbox!')
		return redirect(url_for('settings'))
	except DropboxOAuth2Flow.ProviderException, e:
		logger.log("Auth error: %s" % (e,))
		http_status(403)
		
	
@app.route('/dropboxwebhook', methods=['GET'])
def dropboxverify():
    '''Respond to the webhook verification (GET request) by echoing back the challenge parameter.'''
    return request.args.get('challenge')
	
@app.route('/dropboxwebhook', methods=['POST'])
def dropboxnotification():
	'''Receive a list of changed user IDs from Dropbox and process each.'''

	# Make sure this is a valid request from Dropbox
	signature = request.headers.get('X-Dropbox-Signature')
	if not (signature == hmac.new(app.config['DB_APP_SECRET'], request.data, sha256).hexdigest()):
		abort(403)

	#print request.data
		
	for uid in json.loads(request.data)['delta']['users']:
		
		# if (metadata['is_dir'] or not path.endswith('.md')):
		# see markdown webhook for example, we only want .md files and not folders
		
		puser=BlogBoxUser.query.filter(BlogBoxUser.db_userid==uid).all() 

		for nextuser in puser:
			if (nextuser.ppaid): 
				current_milli_time = int(round(time.time() * 1000))
				taskid = "task-" + str(nextuser.id) + "-" + str(current_milli_time)
				task=autopublish.apply_async(args=[nextuser.id], task_id=taskid)
			
			else:
				nextuser.pdebug="Your blog could not be published because subscription is not active!"
				db.session.commit()
		
	return ''

	
@app.route('/contactus', methods=['GET','POST'])
@login_required
def contactus():
	'''
	contact simply sends the administrator an email message from the currently logged in user
	'''
	if request.method == 'GET':
		puser=g.user
		return render_template('contactus.html', puser=puser)
	else: # POST METHOD
		message_text = request.form['message_text']
		# Send email with the feedback
		message_html = message_text + "<p></p>My site is: " + g.user.psiteurl + "<p></p>My Debug log is: " + g.user.pdebug
		task=queue_email.apply_async(args=[g.user.email,APP_ADMIN_EMAIL,'BlogBox Contact Form',message_html])
		flash("Thankyou - your message has been received. We aim to deal with all support queries within 24 hours")
		return redirect(url_for('settings'))

@app.route('/faq', methods=['GET'])
def faq():
	'''
	FAQ page
	'''
	return render_template('faq.html')
	
@app.route('/signup', methods=['GET'])
def signup():
	'''
	signup page
	'''
	return render_template('signup.html')
	
@app.route('/debug', methods=['GET'])
@login_required
def debug():
	'''
	Debug output
	'''
	puser=g.user
	if (puser.pdebug is not None):
		return render_template('debug.html', puser=puser)
	else:
		return 'None'
	
@app.route('/tandc', methods=['GET'])
def tandc():
	'''
	terms and conditions page
	'''
	return render_template('tandc.html')
		
@app.route('/close_account', methods=['GET'])
@login_required
def close_account():
	'''
	close_account simply flashes a message to tell the user to cancel via paypal.
	'''
	flash('To close your account, please log in to your PayPal account and cancel your subscription.')
	return redirect(url_for('settings'))
		