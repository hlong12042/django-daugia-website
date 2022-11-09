from dataclasses import dataclass
from http.client import HTTPResponse
from queue import Empty
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.template.context_processors import csrf
from django.views.decorators.cache import cache_page
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMessage
from django.db import connection
from django.utils import timezone
from django.conf import settings

from datetime import datetime
from string import ascii_lowercase, ascii_uppercase, digits, punctuation
from collections import Counter

from .forms import ItemImgForm, FormWithCaptcha
from . import models
from .token import account_activation_token

import re, random, magic


def index(req):
    auctions = models.Auction.objects.order_by("-time_begin")
    if len(auctions) > 15:
        auctions = auctions[0, 15]
    return render(req, "index.html", {"auctions": auctions})


def error(req):
    return render(req, "error/error.html")


def register(req):
    if req.method == "POST":
        email = req.POST.get('email')
        password = req.POST.get('password')
        repassword = req.POST.get('repassword')
        captcha = FormWithCaptcha(req.POST)

        if not email or not password or not repassword:
            messages.error(req, "Thiếu thông tin yêu cầu...")
            return redirect("register")

        if not captcha.is_valid():
            messages.error(req, "Bạn chưa xác nhận captcha...")
            return redirect("register")

        # Check email format
        reg_mail = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if not re.fullmatch(reg_mail, email):
            messages.error(req, "Email không hợp lệ...")
            return redirect("register")

        # Check password
        if password_strong_check(password) == False:
            messages.error(req, "Mật khẩu không đạt yêu cầu...")
            return redirect("register")
        if password != repassword:
            messages.error(req, "Nhập lại mật khẩu không khớp...")
            return redirect("register")

        # Check if email is used
        check = models.Account.objects.filter(email=email)
        if check:
            messages.error(req, "Email đã được sử dụng...")
            return redirect("register")

        # Hash password and store new account
        password = make_password(password)
        new_acc = models.Account(email=email, password=password,
                                 is_verified=0, is_blocked=0, time_create=datetime.now())
        new_info = models.Info(account=new_acc)
        try:
            new_acc.save()
            new_info.save()
        except:
            messages.error(req, "Không thể sự dụng email này...")
            return redirect("register")

        # Send activate email
        if not activateEmail(req, new_acc):
            messages.error(
                req, "Mã xác thực không thể gửi đến email của bạn...")
            return redirect("register")

        # If everything is done
        return render(req, "account/activate_email.html")
    else:
        if req.session.get("email"):
            return redirect("/")
        captcha = FormWithCaptcha()
        return render(req, "account/register.html", {"captcha": captcha})


def login(req):
    if req.method == "POST":
        email = req.POST.get('email')
        password = req.POST.get('password')
        captcha = FormWithCaptcha(req.POST)

        if not captcha.is_valid():
            messages.error(req, "Bạn chưa xác nhận captcha...")
            return redirect("login")

        if prevent_bruforce(req, False) == -1:
            messages.error(req, "Do đăng nhập sai quá nhiều lần, chúng tôi buộc phải chặn bạn 15 phút...")
            return redirect("login")

        # Check for email exist
        accs = models.Account.objects.filter(
            email=email, is_verified=1, is_blocked=0)
        if not accs:
            messages.error(req, "Email hoặc mật khẩu không đúng...")
            return redirect("login")

        # Check password
        if not check_password(password, accs[0].password):
            messages.error(req, "Email hoặc mật khẩu không đúng...")
            return redirect("login")

        # If everything is done, store pk of account in session
        prevent_bruforce(req, True)
        req.session['email'] = accs[0].email
        return redirect("/")
    else:
        if req.session.get("email"):
            return redirect("/")
        captcha = FormWithCaptcha()
        return render(req, "account/login.html", {"captcha": captcha})


def logout(req):
    for key in list(req.session.keys()):
        del req.session[key]
    return redirect('index')


def password_strong_check(password):
    # Password length must be at least 8 character
    if len(password) < 8:
        return False

    # And content at least 1 char in echo types of printable characters
    dict1 = Counter(password)
    if len(dict1 & Counter(ascii_lowercase)) == 0:
        return False
    if len(dict1 & Counter(ascii_uppercase)) == 0:
        return False
    if len(dict1 & Counter(digits)) == 0:
        return False
    if len(dict1 & Counter(punctuation)) == 0:
        return False


def activateEmail(req, account: models.Account):
    mail_subject = "Đấu giá PTIT xác thực email của bạn"
    message = render_to_string("account/template_activate_account.html", {
        'domain': get_current_site(req).domain,
        'uid': urlsafe_base64_encode(force_bytes(account.pk)),
        'token': account_activation_token.make_token(account),
        'protocol': 'https' if req.is_secure() else 'http'
    })
    email = EmailMessage(
        mail_subject,
        message,
        to=[account.email])
    if email.send():
        return True
    else:
        return False


def activate(req, uidb64, token):
    account = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        account = models.Account.objects.get(account_id=uid)
    except:
        account = None

    if account is not None and account_activation_token.check_token(account, token):
        account.is_verified = True
        account.save()
        messages.success(
            req, "Tài khoản của bạn đã được xác thực, bạn đã có thể tham gia đấu giá")
    else:
        messages.error(
            req, "Mã xác nhận của bạn sai hoặc đã hết giá trị. Nếu là sai sót hãy liên hệ với chúng tôi để được giải quyết...")
    return redirect('login')


def forgot_password(req):
    if req.method == "POST":
        # Check for account exists
        email = req.POST.get('email')
        captcha = FormWithCaptcha(req.POST)

        if not email:
            messages.error(req, "Bạn chưa nhập email...")
            return redirect("forgot-password")

        if not captcha.is_valid():
            messages.error(req, "Bạn chưa xác nhận captcha...")
            return redirect("forgot-password")
        
        try:
            account = models.Account.objects.get(
                email=email, is_verified=1, is_blocked=0)
        except:
            messages.error(
                req, "Email chưa được đăng ký hoặc chưa được chứng thực...")
        else:
            # New pass is 16 chars which is half-random chosen from printable charaters
            new_pass = ''
            array = ascii_lowercase+ascii_uppercase+digits+punctuation
            for i in range(16):
                new_pass += array[random.randint(0, len(array)-1)]

            # Save new pass
            account.password = make_password(new_pass)
            account.save()
            # Send new pass to mail box of customer
            message = render_to_string("account/template_reset_password.html", {
                "new_pass": new_pass
            })
            email = EmailMessage(
                "Đấu giá PTIT - cấp lại mật khẩu",
                message,
                to=[account.email]
            )
            if email.send():
                messages.success(
                    req, "Mật khẩu mới đã được cấp và gửi về hộp thư của bạn")
            else:
                messages.error(
                    req, "Không thể gửi mật khẩu mới đến email của bạn!")
        return redirect("forgot-password")
    else:
        captcha = FormWithCaptcha()
        return render(req, "account/forgot-password.html", {"captcha": captcha})


def info(req, email):
    # Get info
    session_email = req.session.get("email")
    try: 
        acc = models.Account.objects.get(email=email)
    except:
        return redirect("error")
    in4 = models.Info.objects.get(account=acc)
    auctions = models.Auction.objects.filter(
        auction_detail__attender_id=acc.account_id)

    data = {}
    # Owner review info
    if session_email == acc.email:
        credit_cards = models.Credit_card.objects.filter(
            account__email=email)
        info = {
            "email": email,
            "last_name": in4.last_name,
            "first_name": in4.first_name,
            "time_create": acc.time_create.strftime("%Y-%m-%d"),
            "phone": in4.phone,
            "id_code": in4.id_code,
            "tax_code": in4.tax_code,
            "detail": in4.detail
        }
        data = {
            "info": info,
            "credit_cards": credit_cards,
            "auctions": auctions
        }

    # Guess review info
    else:
        info = {
            "email": email,
            "last_name": in4.last_name,
            "first_name": in4.first_name,
            "time_create": acc.time_create.strftime("%Y-%m-%d"),
            "detail": in4.detail
        }
        data = {
            "info": info,
            "auctions": auctions
        }
    return render(req, "info.html", data)


def change_password(req):
    if req.session.get("email") == None:
        return redirect("error")
    if req.method == "POST":
        oldpassword = req.POST.get('oldpassword')
        password = req.POST.get('password')
        repassword = req.POST.get('repassword')
        captcha = FormWithCaptcha(req.POST)

        if not oldpassword or not password or not repassword:
            messages.error(req, "Bạn chưa nhập đủ thông tin yêu cầu...")
            return redirect("change-password")

        if not captcha.is_valid():
            messages.error(req, "Bạn chưa xác nhận captcha...")
            return redirect("change-password")

        # Check password strength
        if password_strong_check(password) == False:
            messages.error(req, "Mật khẩu không đạt yêu cầu...")
            return redirect("change-password")
        if password != repassword:
            messages.error(req, "Nhập lại mật khẩu không khớp...")
            return redirect("change-password")

        email = req.session.get("email")

        try:
            account = models.Account.objects.get(email=email)
            if not check_password(oldpassword, account.password):
                messages.error(req, "Mật khẩu cũ không đúng...")
                return redirect("change-password")
            account.password = make_password(password)
            account.save()
            messages.success("Thay đổi mật khẩu thành công")
        except:
            return redirect("error")
        return redirect("change-password")
    else:
        captcha = FormWithCaptcha()
        return render(req, "account/change-password.html", {"captcha": captcha})


def history(req, email):
    # Get info
    try:
        session_email = req.session.get("email")
        if session_email != email: 
            return redirect("/error")
        acc = models.Account.objects.get(email=email)
        in4 = models.Info.objects.get(account=acc)
    except:
        return redirect("/error")
    auctions = models.Auction.objects.filter(
        item__creater_id=acc.account_id)
    # Guess review info
    info = {
        "email": email,
        "last_name": in4.last_name,
        "first_name": in4.first_name,
        "time_create": acc.time_create.strftime("%Y-%m-%d"),
        "detail": in4.detail
    }
    data = {
        "info": info,
        "auctions": auctions
    }
    return render(req, "auction/history.html", data)


def create_auction(req):
    try:
        if req.session.get("email") == None:
            raise Exception()
        acc = models.Account.objects.get(email=req.session.get("email"))
    except:
        return redirect("error")

    if req.method == "POST":
        try:
            name = req.POST.get("name")
            price = req.POST.get("price")
            begin = datetime.strptime(req.POST.get("begin"), '%Y-%m-%dT%H:%M')
            end = datetime.strptime(req.POST.get("end"), '%Y-%m-%dT%H:%M')
            detail = req.POST.get("detail")
            img = req.FILES.get("img")

            if not name or not price:
                messages.warning(
                    req, "Bạn chưa nhập đủ thông tin yêu cầu!")
                raise Exception()

            temp = float(price)
            if temp < 0:
                raise Exception()

            if begin < datetime.now():
                messages.warning(
                    req, "Thời gian bắt đầu phải sau thời điểm hiện tại")
                raise Exception()

            if end <= begin:
                messages.warning(
                    req, "Thời gian kết thúc phải sau thời gian bắt đầu")
                raise Exception()

            if "image" not in magic.from_file(img.temporary_file_path(), mime=True):
                messages.warning(
                    req, "File tải lên không đúng định dạng!")
                raise Exception()

            item = models.Item(
                item_name=name,
                time_create=datetime.now(),
                detail=detail,
                first_price=price,
                creater=acc,
                img=img,
            )

            auction = models.Auction(
                time_begin=begin,
                time_end=end,
                item=item,
            )
            item.save()
            auction.save()
            messages.success(req, "Buổi đấu giá đã được tạo thành công!")
        except:
            messages.error(req, "Thông tin không hợp lệ...")

        return redirect("/create-auction")
    else:
        img = ItemImgForm()
        detail = {
            "img": img,
        }
        return render(req, "auction/create-auction.html", {'detail': detail})


def auction(req, id):
    try:
        auc = models.Auction.objects.get(auction_id=id)
    except:
        return redirect("/error")
    
    details = models.Auction_detail.objects.filter(
        auction__auction_id=id).order_by("-price")

    now = datetime.now()
    if auc.time_end < datetime.now() and not auc.winner and details:
        auc.winner = details[0].attender
        auc.save()
    
    params = auc.item.detail.split("\n")
    return render(req, "auction/auction.html", {"auction": auc, "details": details, "now": now, "params": params})


def edit_auction(req, id):
    try:
        if not req.session.get("email"):
            raise Exception()
        auction = models.Auction.objects.get(auction_id=id)
        if auction.item.creater.email != req.session.get("email"):
            raise Exception()
    except:
        return redirect("/error")

    if req.method == "POST":
        try:
            name = req.POST.get("name")
            price = req.POST.get("price")
            begin = datetime.strptime(req.POST.get("begin"), '%Y-%m-%dT%H:%M')
            end = datetime.strptime(req.POST.get("end"), '%Y-%m-%dT%H:%M')
            detail = req.POST.get("detail")
            img = req.FILES.get("img")

            if not name or not price:
                messages.warning(
                    req, "Bạn chưa nhập đủ thông tin yêu cầu...")
                raise Exception()

            temp = float(price)
            if temp < 0:
                raise Exception()

            if begin < datetime.now():
                messages.warning(
                    req, "Thời gian bắt đầu phải sau thời điểm hiện tại")
                raise Exception()

            if end <= begin:
                messages.warning(
                    req, "Thời gian kết thúc phải sau thời gian bắt đầu")
                raise Exception()

            item = models.Item.objects.get(auction__auction_id=id)
            item.item_name = name
            item.first_price = price
            item.detail = detail
            if img: item.img = img
            auction.time_begin = begin
            auction.time_end = end

            item.save()
            auction.save()
            messages.success(req, "Chỉnh sửa thành công!")
        except:
            messages.error(req, "Thông tin không hợp lệ...")

        return redirect("/edit-auction/"+id)
    else:
        img = ItemImgForm()
        detail = {
            "img": img,
        }
        return render(req, "auction/edit-auction.html", {"auction": auction, "detail": detail})


def search(req, page):
    keyword = req.GET.get("keyword")
    if not keyword:
        return redirect("index")
    page = int(page)
    keyword = str(keyword)
    auctions = models.Auction.objects.filter(
        item__item_name__contains=keyword,).order_by('-time_begin')[(page-1)*15:page*15]
    return render(req, "index.html", {"auctions": auctions})


def join_auction(req):
    if req.session.get("email") is None:
        return redirect("/error")

    try:
        email = req.session.get("email")
        auction_id = req.POST.get("auction_id")
        price = int(req.POST.get("price"))
        now = datetime.now()
        acc = models.Account.objects.get(email=email)
        
        if not auction_id:
            return redirect("/error")

        top = models.Auction_detail.objects.filter(
            auction__auction_id=auction_id).order_by("-price")
        if top.exists():
            if top[0].price >= price:
                messages.error(req, "Số tiền bạn dùng vẫn nhỏ hơn top 1...")
                return redirect("/auction/{}".format(auction_id))

        auc = models.Auction.objects.get(auction_id=auction_id)
        if auc.item.first_price >= price:
            messages.error(
                req, "Số tiền bạn dùng vẫn nhỏ hơn giá khởi điểm...")
            return redirect("/auction/{}".format(auction_id))

        if now < auc.time_begin:
            messages.error(
                req, "Buổi đấu giá chưa bắt đầu...")
            return redirect("/auction/{}".format(auction_id))

        if auc.time_end < now:
            messages.error(
                req, "Thời gian đấu giá đã kết thúc, rất lấy làm tiếc...")
            return redirect("/auction/{}".format(auction_id))

        new = models.Auction_detail(
            time=now, attender=acc, auction=auc, price=price)
        new.save()
    except:
        messages.error(req, "Có lỗi xãy ra trong quá trình xử lý...")
    captcha = FormWithCaptcha()
    return redirect("/auction/{}".format(auction_id), {"captcha": captcha})


def check_bank(bank):
    if not bank: 
        return False
    BANK_ARRAY = [
        "AGRIBANK",
        "MBBANK",
        "SACOMBANK",
    ]
    if bank not in BANK_ARRAY:
        return False
    return True


def check_card_code(code):
    if not code: 
        return False
    reg_bank_code = r'\b^[0-9]{16,20}\b'
    if not re.fullmatch(reg_bank_code, code):
        return False
    return True


def check_card_name(name):
    if not name: 
        return False
    reg_bank_name = r'\b^[A-Z ]{5,20}\b'
    if not re.fullmatch(reg_bank_name, name):
        return False
    return True


def add_card(req):
    if req.method=="POST":
        try:
            email = req.session["email"]
            acc = models.Account.objects.get(email=email)
        except:
            return redirect("/error")

        bank = req.POST.get("bank")
        card_code = req.POST.get("card-code")
        card_name = req.POST.get("card-name")

        if not check_bank(bank):
            messages.error(req, "Tên ngân hàng không hợp lệ...")
            return redirect("/info/" + email)

        if not check_card_code(card_code):
            messages.error(req, "Số thẻ không hợp lệ...")
            return redirect("/info/" + email)

        if not check_card_name(card_name):
            messages.error(req, "Tên thẻ không hợp lệ...")
            return redirect("/info/" + email)

        card = models.Credit_card(card_code=card_code, bank=bank, card_name=card_name, is_verified=1, account=acc)
        card.save()
        messages.success(req, "Hoàn thành liên kết thẻ")
    return redirect("/info/" + email)


def prevent_bruforce(req, is_false):
    # Set session for the first time or unblock
    if not req.session.get("service_count") or not is_false:
        service_count = {
            "count": 1,
            "timestamp": datetime.now().timestamp(),
            "is_block": False
        }
        return 1

    session_count = req.session.get("service_count")
    now = datetime.now().timestamp()

    # First is check is blocked
    # If is blocked, the timestamp to block is 15 mins, and increase when another request comes
    if session_count["is_blocked"]:
        if now - service_count["timestamp"] < 15*60:
            service_count["timestamp"] = now
            return -1
        else:
            return prevent_bruforce(req, True)
    
    # If not blocked, the timestamp to increase count is 5s, limit is 5 times
    else:
        if now - service_count["timestamp"] < 5:
            service_count["count"]+=1
            service_count["timestamp"] = now
            if service_count["count"] > 5:
                service_count["is_blocked"]=True
                return -1
            else:
                return 1

        else: 
            return prevent_bruforce(req, True)


def handle_not_found(req, exception):
    return render(req, "error/error.html")


