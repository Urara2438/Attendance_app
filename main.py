from flask import Flask, render_template, redirect, request, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, date
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
import os


app = Flask(__name__)

#関数定義--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def now_jst(): #時間記録
    Tokyo_timezone = pytz.timezone("Asia/Tokyo")
    return datetime.now(Tokyo_timezone)

def cal_age(birthday): #年齢計算
    today = date.today()
    if (today.month, today.day) >= (birthday.month, birthday.day): 
        age = today.year - birthday.year
        return age
    else:
        age = (today.year - birthday.year)-1
        return age
    
def format_work_time(td): #秒数から勤務時間表示
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}時間{minutes}分"


#ログイン機能設定--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
app.config["SECRET_KEY"] = os.urandom(24)
login_manager = LoginManager()
login_manager.init_app(app)
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


#データベースの情報--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
db = SQLAlchemy()
db_info = {
    "user": "postgres",
    "password": "yoneken812",
    "host": "localhost",
    "name": "attendance"
    }
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://{user}:{password}@{host}/{name}".format(**db_info) 
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI 
db.init_app(app)
migrate = Migrate(app, db)


#データベースのテーブル設計--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) #ユーザーID
    username = db.Column(db.String(20), nullable=False)
    birthday = db.Column(db.Date, nullable=False)
    gender = db.Column(db.Integer, nullable=False) #male = 0, female = 1
    phone_number = db.Column(db.String(15), nullable=True)
    email_address = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(500), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=True, default=False)
    
    @property
    def age(self):
        return cal_age(self.birthday)
    
    @property
    def gender_label(self):
        if self.gender == 0:
            return("男性")
        elif self.gender == 1:
            return("女性")
        else:
            return("未設定")
    
class Attend(db.Model):
    id = db.Column(db.Integer, primary_key=True) #勤怠ID
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    work_in = db.Column(db.DateTime)
    work_out = db.Column(db.DateTime)
    status = db.Column(db.Integer, nullable=False, default=0) #退勤済 = 0, 出勤済 = 1


#ログインページ(トップページ)------------------------------------------------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index(): #ログイン機能
    if request.method == "POST":
        email_address = request.form.get("email_address")
        password = request.form.get("password")
        user = Users.query.filter_by(email_address=email_address).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect("/mypage")
        else:
            return render_template("index.html", message="メールアドレスまたはパスワードが間違っています.")
    elif request.method == "GET":
        return render_template("index.html")
    
    
#サインアップ------------------------------------------------------------------------------------------------------------------    
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        gender = request.form.get("gender")
        birthday = datetime.strptime(request.form.get("birthday"),"%Y-%m-%d").date()
        phone_number = request.form.get("phone_number")
        email_address = request.form.get("email_address")
        password = request.form.get("password")
        hashed_pass = generate_password_hash(password)
        user = Users(username = username,
                    gender = gender,
                    birthday = birthday,
                    phone_number = phone_number,
                    email_address = email_address,
                    password = hashed_pass
                    )
        db.session.add(user)
        db.session.commit()
        return redirect("/")
    elif request.method == "GET":
        return render_template("signup.html")


#マイページ------------------------------------------------------------------------------------------------------------------
@app.route("/mypage")
@login_required
def mypage():
    user = Users.query.get(current_user.id)
    all_records = Attend.query.filter_by(user_id=current_user.id).all()
    for record in all_records:
        if record.work_out and record.work_in:
            record.formatted_work_time = format_work_time(record.work_out - record.work_in)
        else:
            record.formatted_work_time = "未確定"
    #勤務中かどうかの判定
    on_work = Attend.query.filter_by(user_id=current_user.id, status=1).first()
    now = now_jst()
    return render_template(
        "mypage.html", 
        user=user, 
        all_records=all_records, 
        on_work=on_work, 
        format_work_time=format_work_time, 
        now=now)  

@app.route("/work_in", methods=["POST"])
@login_required
def work_in():
    attendance = Attend(user_id=current_user.id,
                        work_in=now_jst(),
                        status=1
                        )
    db.session.add(attendance)
    db.session.commit()
    flash("出勤しました．今日も一日頑張りましょう☕️")
    return redirect("/mypage")

@app.route("/work_out", methods=["POST"])
@login_required
def work_out():
    attendance = Attend.query.filter_by(user_id=current_user.id, status=1).first()
    if attendance:
        attendance.work_out = now_jst()
        attendance.status = 0
        db.session.commit()
        flash("退勤しました．お疲れ様でした🍵")
    else:
        flash("⚠️出勤記録が見つかりません．")
    return redirect("/mypage")

@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    user = Users.query.get(current_user.id)
    if request.method == "POST":
        user.username = request.form.get("username")
        user.email_address = request.form.get("email_address")
        user.phone_number = request.form.get("phone_number")
        if request.form.get("password") == "":
            return render_template("edit.html", user=user, message="⚠️パスワードが入力されていません．")
        else:
            user.password = generate_password_hash(request.form.get("password"))
        db.session.commit()
        return redirect("/mypage")
    elif request.method == "GET":
        return render_template("edit.html", user=user)  
             
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


#管理者ページ------------------------------------------------------------------------------------------------------------------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email_address = request.form.get("email_address")
        password = request.form.get("password")
        user = Users.query.filter_by(email_address=email_address).first()
        if user and check_password_hash(user.password, password) and user.is_admin == True:
            login_user(user)
            return redirect("/admin")
        else:
            return render_template("admin_login.html", message="⚠️管理者のメールアドレスまたはパスワードが間違っています．")
    elif request.method == "GET":
        return render_template("admin_login.html")

    
@app.route("/admin")
@login_required
def all_members():
    if current_user.is_admin != True:
        abort(403)  
    else:
        users = Users.query.all()
        #出勤中のメンバーIDを取得
        on_work_user_ids = set()
        on_work_user_records = Attend.query.filter_by(status=1).all()
        for record in on_work_user_records:
            on_work_user_ids.add(record.user_id)
        return render_template("admin.html", users=users, on_work_user_ids=on_work_user_ids)
    
    
@app.route("/details/<int:user_id>")
@login_required
def details(user_id):
    if current_user.is_admin != True:
        abort(403)
    else:
        user = Users.query.get(user_id)
        records = Attend.query.filter_by(user_id=user_id).all() #特定のユーザーのすべての勤怠記録を取得
        for record in records:
            if record.work_out and record.work_in:
                record.formatted_work_time = format_work_time(record.work_out - record.work_in)
            else:
                record.formatted_work_time = "未確定"
        return render_template("details.html", user=user, records=records, format_work_time=format_work_time)


@app.route("/delete_member/<int:user_id>", methods=["POST"])
@login_required
def delete_member(user_id):
    if current_user.is_admin != True:
        abort(403)
    else:
        user = Users.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            return redirect("/admin")
        else:
            abort(404)


    







