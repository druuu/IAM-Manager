from django.shortcuts import render
from django.contrib.auth import logout
from django.http.response import HttpResponse, HttpResponseRedirect
from iam.models import *
from iam.forms import *
import json
import boto3
import csv
from django.core.urlresolvers import reverse
from botocore.exceptions import ClientError
from .forms import CreatePolicyForm


def home(request):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Description:when user hits the url "^home/$" this function is called
    This function renders to "base" template,
    After log in with thier Access keys and Secret Keys.
    '''
    return render(request, "base.html")


def user_logout(request):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Logout
    Description:when user hits the url "^/logout$" this function is called, user gets logged out and redirected to login template.
    Here when user log out respective user access key, secret key, username will be removed from session.
    '''
    if 'access_key' in request.session:
        request.session['access_key'] = None
    if 'secret_key' in request.session:
        request.session['secret_key'] = None
    if 'client_username' in request.session:
        request.session['client_username'] = None
    logout(request)
    return HttpResponseRedirect('/')


def login(request):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:login
    Description:when user hits the url "^$" this function is called
    First this function renders to "login" template,
    Here user login by entering valid access key and secret keys, then these varibles are stored in django session for further use.
    '''

    if request.method == "POST":
        client = boto3.client(
           'iam',
           aws_access_key_id=request.POST.get("access_key"),
           aws_secret_access_key=request.POST.get("secret_key")
        )
        try:
            if request.POST.get("access_key") and request.POST.get("secret_key") and request.POST.get("username"):
                client.get_login_profile(UserName=request.POST.get("username"))
                if 'access_key' not in request.session:
                    request.session['access_key'] = request.POST.get("access_key")
                if 'secret_key' not in request.session:
                    request.session['secret_key'] = request.POST.get("secret_key")
                if 'client_username' not in request.session:
                    request.session['client_username'] = request.POST.get("username")

                data = {"error": False}
            else:
                data = {"error": True, "response": "Please Enter Username, Access key, Secret Key."}
            return HttpResponse(json.dumps(data))

        except ClientError as e:
            data = {"error": True, "response": "Credentials are not valid."}
            return HttpResponse(json.dumps(data))
    if 'access_key' in request.session:
        return HttpResponseRedirect(reverse("home"))
    return render(request, "login.html")


def add_iam_user(request):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Add IAM User
    Description:when user hits the url "^iam/user/add/$" this function is called
    First this function renders to "add_iam_user" template,
    New IAM user can create only when User updated settings(Access key, secret Keys).
    Connecting to boto3 IAM client with AWS Access key and Secret Keys.
    when post data is requested, new IAM user is created, when user selects to generate access and
    secret keys then acess keys are generated and saved in our database.
    '''
    client = boto3.client(
       'iam',
       aws_access_key_id=request.session["access_key"],
       aws_secret_access_key=request.session["secret_key"]
    )

    if request.method == "POST":
        if request.POST.get("username"):
            try:
                if request.POST.get("iam_user_password"):
                    if request.POST.get("password"):
                        try:
                            try:
                                response_without_keys = client.create_user(Path="/", UserName=request.POST.get("username"))
                            except ClientError as e:
                                data = {"error": True, "response": str(e)}
                                return HttpResponse(json.dumps(data))
                            client.create_login_profile(
                                UserName=response_without_keys["User"]["UserName"],
                                Password=request.POST.get("password"),
                                PasswordResetRequired=False
                            )
                        except ClientError as e:
                            data = {"error": True, "response": "Password Should contain atleast one UpperCase letter, LowerCase letter and Numbers."}
                            return HttpResponse(json.dumps(data))
                    else:
                        data = {"error": True, "response": "Please Enter Password"}
                        return HttpResponse(json.dumps(data))
                else:
                    try:
                        response_without_keys = client.create_user(Path="/", UserName=request.POST.get("username"))
                    except ClientError as e:
                        data = {"error": True, "response": str(e)}
                        return HttpResponse(json.dumps(data))

                if request.POST.get("generate_keys"):
                    response = client.create_access_key(UserName=request.POST.get("username"))
                    data = {"error": False, "iam_username": response["AccessKey"]["UserName"], "iam_access_key": response["AccessKey"]["AccessKeyId"], "iam_secret_key": response["AccessKey"]["SecretAccessKey"]}
                else:
                    data = {"error": False, "iam_username": response_without_keys["User"]["UserName"]}
                return HttpResponse(json.dumps(data))
            except ClientError as e:
                data = {"error": True, "response": str(e)}
            return HttpResponse(json.dumps(data))
        else:
            data = {"error": True, "response": "Please enter IAM User Name"}
        return HttpResponse(json.dumps(data))
    return render(request, "iam_user/add_iam_user.html")


def generate_custom_policy(request, user_name):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Create Custom Policy
    Description:when user hits the url "^iam/custom-policy/(<user_name>)/$" this function is called
    First this function renders to "custom_policy" template,
    Here by selecting Amazon service(S3), policy name and provided details custom policy is created.
    Returns Error message for the data invalid or not given correctly.
    '''
    client = boto3.client(
       'iam',
       aws_access_key_id=request.session["access_key"],
       aws_secret_access_key=request.session["secret_key"]
    )
    client_s3 = boto3.client(
        's3',
        aws_access_key_id=request.session["access_key"],
        aws_secret_access_key=request.session["secret_key"])

    response_buckets = client_s3.list_buckets()
    if request.method == "POST":
        create_policy_form = CreatePolicyForm(request.POST)
        if create_policy_form.is_valid():
            if request.POST.get("amazon_s3_service") == "s3":
                bucket_name = str(request.POST.get("bucket_name"))
                l = []
                action = ''
                for index, a in enumerate(request.POST.getlist("action")):
                    action = 's3:'+str(a)
                    l.append(action)
                policy_document = '{"Version": "2012-10-17","Statement": [{"Sid": "","Effect": "Allow","Action": ['+str(l).strip('[]')+'],"Resource": ["arn:aws:s3:::'+bucket_name+'"]}]}'
                policy_document = policy_document.replace("'", '"')
                try:
                    policy = client.create_policy(
                        PolicyName=request.POST.get("policy_name"),
                        PolicyDocument=policy_document
                    )
                    data = {'error': False}
                    return HttpResponse(json.dumps(data))
                except ClientError as e:
                    data = {"error": True, "exception_error": str(e)}
                    return HttpResponse(json.dumps(data))
        else:
            data = {'error': True, 'response': create_policy_form.errors}
        return HttpResponse(json.dumps(data))
    else:
        return render(request, "custom_policy.html", {"user_name": user_name, "response_buckets": response_buckets["Buckets"]})


def iam_user_details_download(request):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Download Access Credentials
    Description:This function generates CSV file download with username, Access Keys, Secret Keys.
    '''
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Credentials.csv"'
    writer = csv.writer(response)
    writer.writerow(["UserName", "AccessKey", "SecretKey"])

    writer.writerow([request.POST.get("download_username"), request.POST.get("download_access_key"), request.POST.get("download_secret_key")])
    return response


def iam_users_list(request):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Add IAM User List
    Description:when user hits the url "^iam/user/list/$" this function is called
    First this function renders to "iam_users_list" template,
    Connecting to boto3 IAM client, Displays all IAM Users.
    '''
    client = boto3.client(
       'iam',
       aws_access_key_id=request.session["access_key"],
       aws_secret_access_key=request.session["secret_key"]
    )
    response = client.list_users()
    return render(request, "iam_user/iam_users_list.html", {"response": response["Users"]})


def iam_user_detail(request, user_name):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Add IAM User Detail
    Description:when user hits the url "^iam/user/detail/$" this function is called
    First this function renders to "iam_users_list" template,
    Connecting to boto3 IAM client, Display details of specific IAM User.
    '''
    client = boto3.client(
       'iam',
       aws_access_key_id=request.session["access_key"],
       aws_secret_access_key=request.session["secret_key"]
    )

    if request.GET.get("generate_keys"):
        response = client.create_access_key(UserName=user_name)
        return HttpResponseRedirect(reverse("iam_user_detail", kwargs={'user_name': user_name}))

    response = client.get_user(UserName=user_name)

    user_policies = client.list_attached_user_policies(
        UserName=response["User"]["UserName"]
    )

    user_access_keys = client.list_access_keys(
        UserName=response["User"]["UserName"],
    )

    return render(request, "iam_user/iam_user_detail.html", {"response": response["User"],
                  "user_policies": user_policies["AttachedPolicies"],
                  "user_name": user_name, "user_access_keys": user_access_keys["AccessKeyMetadata"]})


def iam_user_change_password(request, user_name):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Change password of IAM User
    Description:when user hits the url "^iam/user/change-password/username/$" this function is called
    First this function renders to "change_password" template,
    Connecting to boto3 IAM client, Checks whether the new password and confirm password matches, if not raises an error if not save the data.
    '''
    client = boto3.client(
       'iam',
       aws_access_key_id=request.session["access_key"],
       aws_secret_access_key=request.session["secret_key"]
    )
    if request.method == 'POST':
        if request.POST.get("new_pwd") and request.POST.get("confirm_pwd"):
            if request.POST.get("new_pwd") != request.POST.get("confirm_pwd"):
                data = {"error": True, 'response': "Confirm Password should match with Password."}
                return HttpResponse(json.dumps(data))
            elif request.POST.get("new_pwd") == request.POST.get("confirm_pwd"):
                try:
                    client.create_login_profile(
                        UserName=user_name,
                        Password=request.POST.get("new_pwd"),
                        PasswordResetRequired=False
                    )
                    data = {"error": False}
                    return HttpResponse(json.dumps(data))
                except ClientError as e:
                    data = {"error": True, "response": "Password Should contain atleast one UpperCase letter, LowerCase letter and Numbers."}
                    return HttpResponse(json.dumps(data))
        else:
            data = {'error': True, 'response': "Please enter new password and confirm password."}
            return HttpResponse(json.dumps(data))
    return render(request, 'iam_user/change_password.html')


def policies_list(request, user_name):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Policies list
    Description:when user hits the url "^policies/username/$" this function is called
    First this function renders to "policies" template,
    Connecting to boto3 IAM client,when user can attach multiple policies.
    '''
    client = boto3.client(
       'iam',
       aws_access_key_id=request.session["access_key"],
       aws_secret_access_key=request.session["secret_key"]
    )
    response = client.list_policies(
            Scope='All',
            OnlyAttached=False
            )
    if request.method == "POST":
        for policy in request.POST.getlist("policy"):
            client.attach_user_policy(
                UserName=user_name,
                PolicyArn=policy
            )
        return HttpResponseRedirect(reverse("iam_user_detail", kwargs={'user_name': user_name}))
    return render(request, "policies.html", {"response": response["Policies"], "user_name": user_name})


def detach_user_policies(request, user_name):
    '''
    Authored by:Swetha
    Other Modules Involved:
    Tasks Involved:Policy detach
    Description:when user hits the url "^iam-userpolicy/detach/username/$" this function is called
    First this function renders to 'iam_user_detail' template,
    Connecting to boto3 IAM client,detach policy for the particular user.
    '''
    client = boto3.client(
       'iam',
       aws_access_key_id=request.session["access_key"],
       aws_secret_access_key=request.session["secret_key"]
    )

    client.detach_user_policy(
        UserName=user_name,
        PolicyArn=request.GET.get("policy_arn")
    )
    return HttpResponseRedirect(reverse("iam_user_detail", kwargs={'user_name': user_name}))
