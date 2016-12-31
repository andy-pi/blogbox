## BlogBox  
  
# Introduction  
BlogBox is a web app written in Python Flask, which allows you to save markdown files in dropbox and automatically create a blog.  
BlogBox is based on pelican for markdown to blog conversion. It's a complete app, and has been working on a live site (under a different name), but I decided in the end it wasn't going to make any money so I am open sourcing the code.    
Below are my rough instructions as to how I setup the server and associated services on CentOS 6.5 on a Digital Ocean Server.    
  
# Blurb    
Blogbox is the simplest way to publish on the web. Blogbox makes blogs that are known as static sites, which means they are small and really fast to load.   
Write a blog post in the simple markdown format, save to your dropbox, and blogbox makes your blog including links, menus, blogroll and best of all Blogbox uploads your blog with no need for any help from you.    
Blogbox is Pelican plus dropbox.    
If we refesh the page we can see our post has been added to our blgo without any intervention - it's automagic.     
There's no need to login to BlogBox to add a blog post. But you can log in and change your settings at any time. Site name, title, add links. Blogbox uses disqus for comments and there are 10 themes to choose from and we're going to be adding more as we go.   
You can choose a blogbox sub domain or use your own domain name.    
That's BlogBox, automagically blogging through dropbox.    

# 0. Accounts Required
Digital Ocean  
AWS  
Cloudflare  
Mailgun  
  
# 1. Firewall opening for HTTP traffic  
https://www.digitalocean.com/community/tutorials/iptables-essentials-common-firewall-rules-and-commands  
sudo iptables -A INPUT -p tcp --dport 443 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT  
  
# 2. Installation of python / flask etc  
https://www.digitalocean.com/community/tutorials/how-to-deploy-flask-web-applications-using-uwsgi-behind-nginx-on-centos-6-4  
ON top of my base CentOS 6.5 install  
yum -y update  
yum groupinstall -y development  
yum install -y zlib-devel openssl-devel sqlite-devel bzip2-devel  
  
(python 2.7.6 already on )  
  
Create folders - To keep things simple, we will be following the second option and explicitly state the location of Python interpreter and pip.  
  
(virtualenv -p /home/andy/bin/python2.7 env)  
env/bin/pip install uwsgi  
env/bin/pip install flask  
  
[https://www.digitalocean.com/community/tutorials/how-to-install-nginx-on-centos-6-with-yum]  
sudo yum install epel-release  
sudo yum install nginx  
sudo /etc/init.d/nginx start  
sudo nano /etc/nginx/nginx.conf (comment out location lines)  
sudo /etc/init.d/nginx restart  
sudo chkconfig --level 345 nginx on (autostart)  
env/bin/uwsgi --socket 127.0.0.1:8080 --catch-exceptions -w WSGI:app  
  
  
# 3. Installation of MySQL  
https://www.digitalocean.com/community/tutorials/how-to-install-linux-nginx-mysql-php-lemp-stack-on-centos-6  
sudo yum install mysql-server  
sudo /etc/init.d/mysqld restart  
sudo chkconfig --level 345 mysqld on (autostart)  
  
[WARNING MESSAGE: Initializing MySQL database:  WARNING: The host 'NAME' could not be looked up with resolveip.  
This probably means that your libc libraries are not 100 % compatible  
with this binary MySQL version. The MySQL daemon, mysqld, should work  
normally with the exception that host name resolving will not work.  
This means that you should use IP addresses instead of hostnames  
when specifying MySQL privileges !  
Alternatively you can run which will also give you the option of removing the test  
databases and anonymous user created by default.  This is  
strongly recommended for production servers:  
/usr/bin/mysql_secure_installation  
You can start the MySQL daemon with:  
cd /usr ; /usr/bin/mysqld_safe &  
You can test the MySQL daemon with mysql-test-run.pl  
cd /usr/mysql-test ; perl mysql-test-run.pl]  
  
sudo /usr/bin/mysql_secure_installation  
mysql rootpass: ZZZZZZZZZZZZZZZZZZZZ  
yum -y install mysql-devel (otherwise error on mysql python package install)  
  
  
# 4. Setup mysql database  
mysql -u root -p  
CREATE DATABASE blogbox;  
SHOW DATABASES;  
DROP DATABASE blogbox;  
exit  
  
# 5. Blogbox app installation  
copy files  
env/bin/pip install -r requirements.txt  
env/bin/pip install pelican awscli  
env/bin/pip install pelican  
install themes  
apps/blogbox/env/lib/python2.7/site-packages/pelican/themes  
  
git clone https://github.com/cloudflare-api/python-cloudflare.git  
python setup.py install  
  
http://stackoverflow.com/questions/29134512/insecureplatformwarning-a-true-sslcontext-object-is-not-available-this-prevent  
error on digital ocean due to SSL / python issue when accessing dropbox  
yum install libffi-devel  
env/bin/pip install requests[security]  
  
https://www.digitalocean.com/community/tutorials/how-to-install-and-secure-phpmyadmin-with-nginx-on-an-ubuntu-14-04-server  
  
# 6. Setup AWS  
aws configure --profile blogbox1 (See logins for details)  
($HOME\.aws\credentials)  
  
# 7. Install SSL certs and setup /etc/nginx/nginx.conf  
https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-uwsgi-and-nginx-on-ubuntu-14-04  
https://www.digitalocean.com/community/tutorials/how-to-deploy-python-wsgi-applications-using-uwsgi-web-server-with-nginx  
https://github.com/mking/flask-uwsgi  
http://uwsgi-docs.readthedocs.org/en/latest/tutorials/Django_and_nginx.html  
  
need to change permissions to serve static content from nginx  
  
# 7. Setup migrations and configure database:  
http://blog.miguelgrinberg.com/post/flask-migrate-alembic-database-migration-wrapper-for-flask/page/2#comments  
  
python manager.py db init (new way to init mirgration)  
python blogbox-newuser.py  (add new user andy normal blogbox)  
  
NEW WAY TO UPGRADE using flask-migrate  
copy new models.py  
python manager.py db migrate  
python manager.py db upgrade  
  
# 8. Setup auto backup of database.  
  
To backup db  
backup: # mysqldump -u root -p[root_password] [database_name] > dumpfilename.sql  
restore:# mysql -u root -p[root_password] [database_name] < dumpfilename.sql  
  
# 9. Celery Setup  
Install redis and setup  to autostart  
http://www.saltwebsites.com/2012/install-redis-245-service-centos-6  
https://briansnelson.com/How_to_install_Redis_on_a_Centos_6.4_Server  
http://blog.andolasoft.com/2013/07/how-to-install-and-configure-redis-server-on-centosfedora-server.html  
  
yum install redis  
service redis start  
chkconfig redis on  
chkconfig --list redis  
in venv: pip install celery, pip install redis  
  
# 10. Edit logging file to use SSL:  
/home/andy/lib/python2.7/logging/handlers.py  
http://stackoverflow.com/questions/30770981/logging-handlers-smtphandler-raises-smtplib-smtpauthenticationerror  
  
def emit(self, record):  
    """  
    Overwrite the logging.handlers.SMTPHandler.emit function with SMTP_SSL.  
    Emit a record.  
    Format the record and send it to the specified addressees.  
    """  
    try:  
        import smtplib  
        from email.utils import formatdate  
        port = self.mailport  
        if not port:  
            port = smtplib.SMTP_PORT  
        smtp = smtplib.SMTP_SSL(self.mailhost, port, timeout=self._timeout)  
        msg = self.format(record)  
        msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\n\r\n%s" % (self.fromaddr, ", ".join(self.toaddrs), self.getSubject(record), formatdate(), msg)  
        if self.username:  
            smtp.ehlo()  
            smtp.login(self.username, self.password)  
        smtp.sendmail(self.fromaddr, self.toaddrs, msg)  
        smtp.quit()  
    except (KeyboardInterrupt, SystemExit):  
        raise  
    except:  
        self.handleError(record)  
		  
IMPROVEMENTS:  
https://realpython.com/blog/python/python-web-applications-with-flask-part-iii/#logging  
  
# 11. Setup uWSGI flask to autostart as a daemon with init.d centos  
https://www.linode.com/docs/websites/nginx/wsgi-using-uwsgi-and-nginx-on-centos-5  
  
useradd -M -r --shell /bin/sh --home-dir /opt/uwsgi uwsgi  
/etc/init.d/uwsgi http://www.linode.com/docs/assets/701-init-rpm.sh  
# needs mods  
sudo chmod +x /etc/init.d/uwsgi  
  
sudo mkdir /opt/uwsgi  
sudo chown -R uwsgi:uwsgi /opt/uwsgi  
sudo touch /var/log/uwsgi.log  
sudo chown uwsgi /var/log/uwsgi.log  
  
sudo chkconfig --add uwsgi  
sudo chkconfig uwsgi on  
/etc/init.d/uwsgi start OR  
sudo service uwsgi start  
  
# 12. celery worker as daemon  
http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html#daemonizing  
https://github.com/celery/celery/blob/3.1/extra/centos/celeryd  
  
/etc/init.d/celeryd - see saved file  
sudo chmod +x /etc/init.d/celeryd  
/etc/default/celeryd - see saved file  
sudo chkconfig --add celeryd  
sudo chkconfig celeryd on  
sudo service celeryd start  
  
# 13. Manually start/stop instructions:  
  
cd apps/blogbox  
source env/bin/activate  
celery worker -A app.celery --loglevel=info &  
sudo kill -SIGKILL <pid>  
env/bin/uwsgi --socket 127.0.0.1:8080 --die-on-term --master --processes 4 --catch-exceptions -w WSGI:app &  
  
sudo service celeryd restart  
sudo service uwsgi restart  