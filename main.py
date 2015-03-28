import os
import re
import random
import hashlib
import hmac
from string import letters
import mimetypes
import webapp2
import jinja2
from google.appengine.ext import db
import webbrowser
from urllib2 import urlopen
import requests
from bs4 import BeautifulSoup
import json
import html5lib
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),autoescape = True)
secret = 'fart'
def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)
def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())
def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val
        
class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)
    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))
    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header('Set-Cookie','%s=%s; Path=/' % (name, cookie_val))
    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)
    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))
    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')
    def render_json(self, d):
        json_txt = json.dumps(d)
        self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
        self.write(json_txt)
    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))
        
class MainPage(Handler):
    def get(self):
        self.render("home.html")
        
def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))
def make_pw_hash(name, pw, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)
def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)
def users_key(group = 'default'):
    return db.Key.from_path('users', group)
         
class User(db.Model):
    name = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)
    email = db.StringProperty()
    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent = users_key())
    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).get()
        return u
    @classmethod
    def register(cls, name, pw, email = None):
        pw_hash = make_pw_hash(name, pw)
        return User(parent = users_key(),name = name,pw_hash = pw_hash,email = email)
    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u
            
USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)
PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)
EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)

class Signup(Handler):
    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')
        params = dict(username = self.username,email = self.email)
        if not valid_username(self.username):
            params['error_username'] = "That's not a valid username."
            have_error = True
        if not valid_password(self.password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True
        if not valid_email(self.email):
            params['error_email'] = "That's not a valid email."
            have_error = True
        if have_error:
            self.render('home.html', **params)
        else:
            self.done()
    def done(self, *a, **kw):
        raise NotImplementedError

class Register(Signup):
    def done(self):
        #make sure the user doesn't already exist
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists.'
            self.render('home.html', error_username = msg)
        else:
            u = User.register(self.username, self.password, self.email)
            u.put()
            self.login(u)
            self.redirect('/')

class Login(Handler):
    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        u = User.login(username, password)
        if u:
            self.login(u)
            frontuser = username
            self.redirect('/')
        else:
            msg = 'Invalid login'
            self.render('home.html', error = msg)

class Logout(Handler):
    def get(self):
        self.logout()
        self.redirect('/')
        
class NewBooks(Handler):
    def get(self):
        self.render("newbooks.html")
    def post(self):
        branch = self.request.get("branch")
        semester = self.request.get("semester")
        publications = self.request.get("publications")
        subject = self.request.get("subject")
        if semester:
            yo = int(semester)
        if(branch and semester and publications and subject):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp)
        elif(branch and semester and publications):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp) 
        elif(branch and semester and subject):
            disp = Books.all().filter("branch =", branch).filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp)  
        elif(branch and publications and subject):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).filter("name =", subject).fetch(10)
            self.render("newbooks.html", disp = disp)
        elif(semester and publications and subject):
            disp = Books.all().filter("publisher =", publications).filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp)
        elif(branch and semester):
            disp = Books.all().filter("branch =", branch).filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp)
        elif(semester and publications):
            disp = Books.all().filter("publisher =", publications).filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp)  
        elif(publications and subject):
            disp = Books.all().filter("publisher =", publications).filter("name =", subject).fetch(10)
            self.render("newbooks.html", disp = disp)
        elif(branch and subject):
            disp = Books.all().filter("branch =", branch).filter("name =", subject).fetch(10)
            self.render("newbooks.html", disp = disp) 
        elif(branch and publications):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).fetch(10)
            self.render("newbooks.html", disp = disp)
        elif(semester and subject):
            disp = Books.all().filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp) 
        elif(branch):
            disp = Books.all().filter("branch =", branch).fetch(10)
            self.render("newbooks.html", disp = disp) 
        elif(semester):
            disp = Books.all().filter("semester =", yo).fetch(10)
            self.render("newbooks.html", disp = disp)
        elif(publications):
            disp = Books.all().filter("publisher =", publications).fetch(10)
            self.render("newbooks.html", disp = disp)  
        elif(subject):
            disp = Books.all().filter("name =", subject).fetch(10)
            self.render("newbooks.html", disp = disp)
        else:
            self.render("newbooks.html")

class OldBooks(Handler):
    def get(self):
        self.render("oldbooks.html")
    def post(self):
        branch = self.request.get("branch")
        semester = self.request.get("semester")
        publications = self.request.get("publications")
        subject = self.request.get("subject")
        if semester:
            yo = int(semester)
        if(branch and semester and publications and subject):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp)
        elif(branch and semester and publications):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp) 
        elif(branch and semester and subject):
            disp = Books.all().filter("branch =", branch).filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp)  
        elif(branch and publications and subject):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).filter("name =", subject).fetch(10)
            self.render("oldbooks.html", disp = disp)
        elif(semester and publications and subject):
            disp = Books.all().filter("publisher =", publications).filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp)
        elif(branch and semester):
            disp = Books.all().filter("branch =", branch).filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp)
        elif(semester and publications):
            disp = Books.all().filter("publisher =", publications).filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp)  
        elif(publications and subject):
            disp = Books.all().filter("publisher =", publications).filter("name =", subject).fetch(10)
            self.render("oldbooks.html", disp = disp)
        elif(branch and subject):
            disp = Books.all().filter("branch =", branch).filter("name =", subject).fetch(10)
            self.render("oldbooks.html", disp = disp) 
        elif(branch and publications):
            disp = Books.all().filter("branch =", branch).filter("publisher =", publications).fetch(10)
            self.render("oldbooks.html", disp = disp)
        elif(semester and subject):
            disp = Books.all().filter("name =", subject).filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp) 
        elif(branch):
            disp = Books.all().filter("branch =", branch).fetch(10)
            self.render("oldbooks.html", disp = disp) 
        elif(semester):
            disp = Books.all().filter("semester =", yo).fetch(10)
            self.render("oldbooks.html", disp = disp)
        elif(publications):
            disp = Books.all().filter("publisher =", publications).fetch(10)
            self.render("oldbooks.html", disp = disp)  
        elif(subject):
            disp = Books.all().filter("name =", subject).fetch(10)
            self.render("oldbooks.html", disp = disp)
        else:
            self.render("oldbooks.html")
  
class Books(db.Model):
    prod_id = db.StringProperty()
    name = db.StringProperty()
    semester = db.IntegerProperty()
    author = db.StringProperty()
    stock = db.IntegerProperty()
    actual_price = db.IntegerProperty()
    discount_price = db.IntegerProperty()
    branch = db.StringProperty()
    publisher = db.StringProperty()
    publishing_date = db.StringProperty()
    edition = db.StringProperty()
    
    def as_dict(self):
        d = {'name': self.name,
             'author': self.author,
			 'actual_price': self.actual_price,
			 'publisher': self.publisher}
        return d
    
class Orders(db.Model):
    cust_name = db.StringProperty()
    address = db.PostalAddressProperty()
    college = db.StringProperty()
    book_name = db.StringProperty()
    quantity = db.IntegerProperty()
    total_amount = db.IntegerProperty()
    contact_no = db.IntegerProperty()
    book_id = db.StringProperty()
    email_id = db.EmailProperty()

"""
d = Orders(cust_name = "Manas Chaturvedi", address = "Borivali", college = "TCET",
           book_name = "OOSE", quantity = 1, total_amount = 325, contact_no = 9022380436,
           book_id = "oose.jpeg", email_id = "manas.oid@gmail.com")
d.put()    
      


a = Books(prod_id = "oose.jpeg", name = "Object Oriented Software Engineering",
          semester = 6, author = "Bernard Bruegge, Allen H. Dutoit", stock = 5,
          actual_price = 325, discount_price = 275, branch = "Computers",
          publisher = "Pearson", publishing_date = "2010", edition = "2013")
a.put()

a2 = Books(prod_id = "dwm.png", name = "Data Warehouse and Data Mining",
          semester = 6, author = "Aarti Deshpande", stock = 5,
          actual_price = 315, discount_price = 260, branch = "Computers",
          publisher = "Techmax", publishing_date = "2010", edition = "2013")
a2.put()


a3 = Books(prod_id = "cg.jpeg", name = "Computer Graphics",
          semester = 4, author = "A.P. Godse, D.A. Godse", stock = 2,
          actual_price = 330, discount_price = 280, branch = "Computers",
          publisher = "Techmax", publishing_date = "2010", edition = "2013")
a3.put()

a4 = Books(prod_id = "spccjohn.jpeg", name = "System Programming and Compiler Construction",
          semester = 6, author = "John Donovan", stock = 2,
          actual_price = 410, discount_price = 355, branch = "Computers",
          publisher = "Tata McGraw Hill", publishing_date = "2010", edition = "2013")
a4.put()


a5 = Books(prod_id = "1.jpg", name = "Advanced Microprocessors",
          semester = 6, author = "J. S. Katre", stock = 2,
          actual_price = 320, discount_price = 290, branch = "Computers",
          publisher = "Techmax", publishing_date = "2010", edition = "2013")
a5.put()


a6 = Books(prod_id = "ampburchandi.gif", name = "Advanced Microprocessors",
          semester = 6, author = "K.M. Burchandi, A.K. Ray", stock = 2,
          actual_price = 390, discount_price = 355, branch = "Computers",
          publisher = "Tata McGraw Hill", publishing_date = "2010", edition = "2013")
a6.put()

a7 = Books(prod_id = "CN.jpg", name = "Computer Networks",
          semester = 5, author = "Andrew Tenenbaum", stock = 1,
          actual_price = 390, discount_price = 355, branch = "Computers",
          publisher = "Tata McGraw Hill", publishing_date = "2010", edition = "2013")
a7.put()

a8 = Books(prod_id = "mp.jpeg", name = "Microprocessors and Interfacing",
          semester = 5, author = "J. S. Katre", stock = 2,
          actual_price = 320, discount_price = 290, branch = "Computers",
          publisher = "Techmax", publishing_date = "2010", edition = "2013")
a8.put()

"""
  
class Template(Handler):
    def get(self):
        k = self.request.get("key")
        disp=Books.all().filter("prod_id =", k).get()
        self.render("template.html", disp = disp)
    def post(self):
        if self.user:
            qua = self.request.get("quantity")
            if not qua:
                k = self.request.get("key")
                disp=Books.all().filter("prod_id =", k).get()
                params = dict()
                params['error_quantity'] = "That's not a valid quantity."
                self.render("template.html", disp = disp, **params)
            else:
                quantity = int(qua)
                k = self.request.get("key")
                disp=Books.all().filter("prod_id =", k).get()
                self.redirect('/cart?quantity=%s&key=%s' % (quantity,k))
        else:
            k = self.request.get("key")
            disp=Books.all().filter("prod_id =", k).get()
            params = dict()
            params['error_user'] = "please login to procced"
            self.render("template.html", disp = disp, **params)

class Cart(Handler):
    def get(self): 
        qu = self.request.get("quantity")
        quantity = int(qu)
        k = self.request.get("key")
        disp = Books.all().filter("prod_id =", k).get()       
        self.render("cart.html", disp = disp, quantity = quantity)       
    def post(self):
        if self.user:
            qua = self.request.get("quantity")
            quantity = int(qua)
            k = self.request.get("key")
            disp=Books.all().filter("prod_id =", k).get()
            self.redirect('/order?quantity=%s&key=%s' % (quantity,k))
        else:
            k = self.request.get("key")
            qu = self.request.get("quantity")
            quantity = int(qu)
            disp=Books.all().filter("prod_id =", k).get()
            params = dict()
            params['error_user'] = "please login to procced"
            self.render("cart.html", disp = disp, quantity = quantity, **params)  
            
class Order(Handler):
    def get(self):
        qu = self.request.get("quantity")
        quantity = int(qu)
        k = self.request.get("key")
        disp = Books.all().filter("prod_id =", k).get()       
        self.render("order1.html", disp = disp, quantity = quantity)
    def post(self):
        if self.user:
            cust_name = self.request.get("cusname")
            address = self.request.get("address")
            college = self.request.get("college")
            book_name = self.request.get("book_name")
            qua = self.request.get("quant")       
            tot_amount = self.request.get("tot_amount")
            cont = self.request.get("mobile")        
            book_id = self.request.get("book_id")
            email_id = self.request.get("email")
            if(cust_name and address and college and book_name and qua and tot_amount  and cont and book_id and email_id):
                quantity = int(qua)
                total_amount = int(tot_amount)
                contact_no = int(cont)
                ordered = Orders(cust_name = cust_name, address = address, college = college,
                                book_name = book_name, quantity = quantity, total_amount = total_amount, 
                                contact_no = contact_no, book_id = book_id, email_id = email_id)
                ordered.put()   
                self.redirect("/successful_order")
            else:
                k = self.request.get("key")
                qu = self.request.get("quantity")
                quantity = int(qu) 
                disp=Books.all().filter("prod_id =", k).get()
                params = dict()
                params['error_form'] = "please fill all the order details"
                self.render("order1.html", disp = disp, quantity = quantity, **params)
        else:
            k = self.request.get("key")
            qu = self.request.get("quantity")
            quantity = int(qu)
            disp=Books.all().filter("prod_id =", k).get()
            params = dict()
            params['error_user'] = "please login to procced"
            self.render("order1.html", disp = disp, quantity = quantity, **params)
        
class ContactUs(Handler):
    def get(self):
        self.render("cont.html")
                
class AboutUs(Handler):
    def get(self):
        self.render("aboutus.html")
        
class SuccessOrder(Handler):
    def get(self):
        self.render("successorder.html")
        
class AjaxHandler(Handler):
    def get(self):
        self.response.write("If you can read this message, do know that Ajax is working tirelessly behind the scenes to load this data dynamically ! ")  
        
class GGHandler(Handler):
    def get(self):
        self.render("gg.html")    

class SearchHandler(Handler):
    def get(self):
		self.render("search.html")
    def post(self):
		keey = self.request.get('keey')
		url = "http://www.amazon.in/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=" + str(keey)
		url1 = "http://books.rediff.com/" + str(keey) + "?sc_cid=books_inhomesrch"
		ss = requests.get(url)
		ss1 = requests.get(url1)
		src = ss.text
		src1 = ss1.text
		obj = BeautifulSoup(src, 'html5lib')
		obj1 = BeautifulSoup(src1, 'html5lib')
		li = []
		ai = []
		for e in obj.findAll("span", {'class' : 'lrg bold'}):
			title = e.string
			li.append(title)
		for e in obj1.findAll("a", {'class' : 'bold'}):
			title = e.string
			ai.append(title)
		self.render("searchresult.html", li = li, ai = ai, keey = keey)

class RSSHandler(Handler):
    def get(self):
        rsss = Books.all().fetch(1000)
        rss = list(rsss) 
        return self.render_json([p.as_dict() for p in rss])

class EbayHandler(Handler):
    def get(self):
        
                
app = webapp2.WSGIApplication([('/', MainPage),
                                ('/signup', Register),
                                ('/login', Login),
                                ('/logout', Logout),
                                ('/template', Template),
                                ('/newbooks', NewBooks),
                                ('/contactus', ContactUs),
                                ('/aboutus', AboutUs),
                                ('/oldbooks',OldBooks),
                                ('/order',Order),
                                ('/successful_order', SuccessOrder),
                                ('/cart',Cart),
                                ('/ajax', AjaxHandler),
                                ('/tcet', GGHandler),
								('/search', SearchHandler),
								('/rss', RSSHandler),
								('/ebay', EbayHandler)], debug=True)