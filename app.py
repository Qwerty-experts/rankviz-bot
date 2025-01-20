from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import os
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
import time
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import uuid
from langchain_core.messages import HumanMessage
import jwt
load_dotenv()

app=Flask(__name__)

os.environ['GROQ_API_KEY'] = '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'
os.environ['GOOGLE_API_KEY'] = 'AIzaSyAke4hturZTQtCvS0SLA00t0rD5MJifhW4'
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app.secret_key = os.urandom(24)  

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['MONGO_URI'] = 'mongodb://localhost:27017/rankvizdatabase'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'ethicalgan@gmail.com'
app.config['MAIL_PASSWORD'] = 'rehg hjfx tauh zrof'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.secret_key = "supersecretkey"
mongo = PyMongo(app)
mail = Mail(app)

def generate_token(user):
    payload = {
        'email': user['email'],
        'time': time.time()
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip()
    password = request.form['password']
    print(email)
    print(password)
    user = mongo.db.users.find_one({'email': email})
    if user and check_password_hash(user['password'], password):
        session['email'] = email
        session['token'] = generate_token(user)
        print('current_token is ',session['token'])
        return redirect(url_for('index'))
    else:
        flash('Invalid username or password.')
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session['token'] = None
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()  
        user = mongo.db.users.find_one({'email': email})  
        
        if user:
            # Generate a token
            token = str(uuid.uuid4())
            mongo.db.password_reset_tokens.insert_one({
                'email': email,  
                'token': token,
            })

            # Generate the reset URL
            reset_url = url_for('reset_password', token=token, _external=True)

            # Create a message to send the email
            msg = Message('Password Reset Request',
                          sender='ethicalgan@gmail.com',
                          recipients=[email])
            msg.body = f'Click the following link to reset your password: {reset_url}'

            try:
                mail.send(msg)  # Send the email
                flash('A password reset link has been sent to your email.', 'info')
            except Exception as e:
                flash(f'Error sending email: {str(e)}', 'danger')
        else:
            flash('Email not found. Please check the email address.', 'danger')

        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    print(token)
    if request.method == 'POST':
        new_password = request.form['password']
        reset_token = mongo.db.password_reset_tokens.find_one({'token': token})

        email = reset_token['email']
        hashed_password = generate_password_hash(
            new_password, method='pbkdf2:sha256')
        mongo.db.users.update_one({'email': email}, {
                                  '$set': {'password': hashed_password}})
        mongo.db.password_reset_tokens.delete_one({'token': token})
        flash('Password has been reset successfully! You can now log in.')
        return redirect(url_for('home'))

    return render_template('reset_password.html', token=token)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']
        print(email)
        print(password)
        # Check if the username already exists in the database
        existing_user = mongo.db.users.find_one({'email': email})

        if existing_user:
            flash('Username already exists. Please choose a different username.')
            return redirect(url_for('signup'))
        # If username does not exist, proceed to create a new user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        mongo.db.users.insert_one({'email': email, 'password': hashed_password})
        flash('Signup successful! Please log in.')
        return redirect(url_for('home'))
    return render_template('signup.html')

llm = ChatGroq(groq_api_key = GROQ_API_KEY,
               model_name = "Llama3-8b-8192")



prompt = ChatPromptTemplate.from_template("""You are an experienced SEO and digital marketing professional specializing in crafting personalized proposals. Your goal is to write a compelling proposal for the following job post.
Job post:{input}
Previous Context(if any):{context}

CRITICAL RULES:
1. NEVER use phrases like "I'm thrilled," "I'm excited", "As a seasoned SEO professional" or any similar enthusiasm expressions
2. Only use case studies and portfolio examples explicitly provided below
3. Make it short


Opening Alternatives (Use these instead of "I'm thrilled," "I'm excited, "As a seasoned SEO professional"):
- "Based on your requirements..."
- "After reviewing your project needs..."
- "Your project aligns perfectly with..."
- "Having analyzed your requirements..."

Key Guidelines:
Guidelines:
1. Write a natural, conversational proposal of 150-200 words and donot use workds like "I'd be thrilled" or "I am excited" Instead, vary the introduction to feel fresh and client-specific.
2. Start with a personalized greeting that matches the job post's tone
3. Choose the appropriate scenario based on website availability:
   - If website URL is provided: Mention specific improvements needed
   - If no website URL: Request the URL professionally
   - If multiple projects: Suggest a discovery call

Required Sections:
1. Opening (Avoid "I'd be thrilled" or similar generic starts)
2. Relevant case studies (2-3 from provided list matching client's industry) take only those that are provided in the prompt and donot use any other case studies that are not provided in the prompt or mentioned about it in the response.
3. Action plan (3-4 specific steps)
4. Portfolio examples that are provided in the prompt and donot use any other portfolio examples that are not provided in the prompt or mentioned about it in the response.
5. Clear call-to-action

Available Resources:
{{
    "audit_links": [
        "https://bit.ly/3L2710d",
        "https://bit.ly/3XJqKt4"
    ],
    "case_studies": {{
        "saas": {{
            "url": "https://bit.ly/3StIZPL",
            "growth": "597%"
        }},
        "ecommerce": {{
            "url": "https://bit.ly/45EoiGp",
            "growth": "270%"
        }},
        "local": {{
            "url": "https://bit.ly/3zovcUc",
            "growth": "200%"
        }},
        "local_gmb": {{
            "url": "https://bit.ly/49zWoNO",
            "growth": "61% views, 233% organic"
        }},
        "blog": {{
            "url": "https://bit.ly/3zekcbG",
            "growth": "297%"
        }}
    }},
    "content_samples": [
        "https://bit.ly/3WAlxS7",
        "https://bit.ly/4cvGEM4"
    ],
    "seo_resources": {{
        "local_seo": "https://bit.ly/3X9WA0e",
        "keyword_research": "https://bit.ly/3sgk2dc",
        "keyword_gap": "https://bit.ly/3lAaeaw"
    }},
    "backlink_samples": {{
        "forum_comments": "https://bit.ly/3gkuGtD",
        "guest_posts": "https://bit.ly/3s7LUkj",
        "white_hat": "https://bit.ly/3oMU82h",
        "link_exchange": "https://bit.ly/3XSR9Bs"
    }},
    "technical_resources": {{
        "citations": "https://bit.ly/3EXO3m4",
        "web_development": "https://bit.ly/3xCrUMw",
        "redirection": "https://bit.ly/4blbUwe"
    }},
    "portfolio_websites_links": [
        "http://fastlabourhire.com.au",
        "https://uniprint.net/",
        "https://processfusion.com/",
        "https://edenderma.com",
        "https://fleminghowland.com/"
    ]
}}

Remember to:
- Keep the tone professional but conversational
- Use only provided metrics and links
- Avoid generic phrases and repetitive structures like "I'd be thrilled" or "I am excited"
- Focus on client's specific needs and industry
- Do not use email formatting or headers
- Write in a flowing, natural paragraph style
- Please follow the criteria
- Please stick to the output
- Do not include any additional information that is not provided in the prompt
- Do not include any placeholder
- Always include links from `Available Resources` section based on the criteria from the prompt
""")


def vector_embedding():
    if "vectors" not in app.config:
        app.config['embeddings'] = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        app.config['loader'] = PyPDFDirectoryLoader("./data")
        app.config['docs'] = app.config['loader'].load()
        app.config['text_splitter'] = RecursiveCharacterTextSplitter(chunk_size = 10000,chunk_overlap = 1000)
        app.config['final_documents'] = app.config['text_splitter'].split_documents(app.config['docs'][:])
        app.config['vectors'] = FAISS.from_documents(app.config['final_documents'],app.config['embeddings'])


vector_embedding()  

# Route for the homepage
@app.route('/chatbot', methods=['GET', 'POST'])
def index():
    token = session['token']
    print('current_token in chatbot is: ',token)
    if token is None:
        flash('You are not authorized to access this page.')
        return redirect(url_for('home'))

    if 'messages' not in app.config:
        app.config['messages'] = []

    if request.method == 'POST':
        question = request.form.get('question') or request.json.get('question')
        print("Question:", question)

        document_chain = create_stuff_documents_chain(llm, prompt)
        retriever = app.config["vectors"].as_retriever()
        retrieval_chain = create_retrieval_chain(retriever, document_chain)
        start = time.process_time()  
        response = retrieval_chain.invoke({'input': question})['answer']
        print("Raw response:", response)
        response_time = time.process_time() - start
        print("Response time: ", time.process_time() - start)
        # print("Answer:", response['answer'])
        # response += f" (Response Time: {response_time:.2f} seconds)"

        app.config['messages'].append((question, response))
        
        print(app.config['messages'])
        
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'question': question, 'response': response})

    return render_template('index.html', messages=app.config.get('messages', []))

if __name__ == '__main__':
    app.run(port=8006)