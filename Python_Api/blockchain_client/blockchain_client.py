from collections import OrderedDict

import binascii

import Crypto
import Crypto.Random
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

import pymongo
import hashlib

import requests
from flask import Flask, jsonify, request, render_template

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["vote"]
mycol = mydb["voter"]


class Transaction:

    def __init__(self, sender_address, sender_private_key, recipient_address, value):
        self.sender_address = sender_address
        self.sender_private_key = sender_private_key
        self.recipient_address = recipient_address
        self.value = value

    def __getattr__(self, attr):
        return self.data[attr]

    def to_dict(self):
        return OrderedDict({'sender_address': self.sender_address,
                            'recipient_address': self.recipient_address,
                            'value': self.value})

    def sign_transaction(self):
        """
        Sign transaction with private key
        """
        private_key = RSA.importKey(binascii.unhexlify(self.sender_private_key))
        signer = PKCS1_v1_5.new(private_key)
        h = SHA.new(str(self.to_dict()).encode('utf8'))
        return binascii.hexlify(signer.sign(h)).decode('ascii')


app = Flask(__name__)


# app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = 'pera@mituniversity.edu.in'  # enter your email here
# app.config['MAIL_DEFAULT_SENDER'] = 'todo.dotoz123@gmail.com'  # enter your email here
# app.config['MAIL_PASSWORD'] = 'asdf@123'  # enter your password here


@app.route('/')
def index():
    return render_template('./index.html')


@app.route('/login', methods=['PUT', 'POST'])
def login():
    body = request.json
    if request.method == "POST":
        d = mycol.find_one({"$and": [{"aadhar": body.get("aadhar")},
                                     {"pass": hashlib.md5((body.get("pass")).encode()).hexdigest()}]},
                           {"_id": 0, "aadhar": 1, "voter": 1, "public_key": 1, "private_key": 1, "is_verified": 1,
                            "is_active": 1})
        if d is not None:
            return jsonify(
                {"error": False, "key": "0", "voter": d["voter"], "aadhar": d["aadhar"], "pubkey": d["public_key"],
                 "prikey": d["private_key"],
                 "err_msg": "Successful"})
        return jsonify({"error": True, "err_msg": "Invalid Credentials"})
    elif request.method == "PUT":
        d = mycol.find_one({"$and": [{"aadhar": body.get("aadhar")},
                                     {"voter": body.get("voter")}]},
                           {"_id": 0, "aadhar": 1, "voter": 1, "balance": 1, "is_verified": 1, "is_active": 1})
        # mail_handler.send_mail(d["email"], d["username"], 'Verification Code.', mycol)
        d["error"] = False
        d["total"] = 0
        e = []
        res = mycol.find({"wallet_type": "party"},
                         {"_id": 0, "aadhar": 1, "voter": 1, "party": 1, "balance": 1})
        for i in res:
            d["total"] += i["balance"]
            e.append(i)
        for i in range(len(e)):
            e[i]["percent"] = float(e[i]["balance"] / d["total"])
        d["party"] = e
        return jsonify(d)
    return jsonify({"error": True, "err_msg": "Invalid Request"})


@app.route('/register', methods=['POST'])
def signup():
    if request.method == 'POST':
        body = request.json
        print(body)
        # aadhar = hashlib.md5(body.get("aadhar").encode()).hexdigest()
        # voter = hashlib.md5(body.get("voter").encode()).hexdigest()
        aadhar = body.get("aadhar")
        voter = body.get("voter")
        passwd = hashlib.md5(body.get("pass").encode()).hexdigest()
        d = mycol.find_one({"$or": [{"aadhar": aadhar}, {"voter": voter}]}, {"_id": 0})
        print(d)
        if d is None:
            d = {"aadhar": aadhar, "voter": voter, "pass": passwd, "is_verified": False,
                 "is_active": True}
            res = new_wallet(aadhar + voter)
            d["public_key"] = res["public_key"]
            d["private_key"] = res["private_key"]
            d["balance"] = res["balance"]
            res = mycol.insert_one(d)
            print(str(res.inserted_id))
            # d = mycol.find_one({"$or": [{"username": body.get("email")}, {"email": body.get("email")}]})
            # send_mail(d["email"], aadhar, 'Activate your account.', mycol)
            return jsonify({"error": False, "err_msg": "Wallet Created Successfully"})
        else:
            return jsonify({"error": True, "err_msg": "wallet already exist"})
    else:
        return jsonify({"error": True, "err_msg": "Invalid Request"})


@app.route('/make/transaction')
def make_transaction():
    return render_template('./make_transaction.html')


@app.route('/view/transactions')
def view_transaction():
    return render_template('./view_transactions.html')


@app.route('/wallet/new', methods=['GET'])
def new_wallet(key=00000000):
    random_gen = Crypto.Random.new(key).read
    private_key = RSA.generate(1024, random_gen)
    public_key = private_key.publickey()
    response = {
        'private_key': binascii.hexlify(private_key.exportKey(format='DER')).decode('ascii'),
        'public_key': binascii.hexlify(public_key.exportKey(format='DER')).decode('ascii'),
        'balance': 1  # "1".encode(encoding='UTF-8', errors='strict')
    }
    return response


@app.route('/generate/transaction', methods=['POST'])
def generate_transaction():
    if request.method == 'POST':
        body = request.json
        sender_address = body.get("sender_address")
        sender_private_key = body.get("sender_private_key")
        recipient_address = body.get("recipient_address")
        value = body.get("amount")

        transaction = Transaction(sender_address, sender_private_key, recipient_address, value)

        response = {'transaction': transaction.to_dict(), 'signature': transaction.sign_transaction(),'error':False}
        return jsonify(response), 200
    else:
        return jsonify({"error": True, "err_msg": "Invalid Request"})


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=8080, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='172.22.120.132', port=port, debug=True)  # app.run(host='127.0.0.1', port=port)
