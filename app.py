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
load_dotenv()

app=Flask(__name__)

os.environ['GROQ_API_KEY'] = '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'
os.environ['GOOGLE_API_KEY'] = 'AIzaSyAke4hturZTQtCvS0SLA00t0rD5MJifhW4'
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app.secret_key = os.urandom(24)  # Required for flashing messages

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
        return redirect(url_for('index'))
    else:
        flash('Invalid username or password.')
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
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
                'email': email,  # Store the token with the email
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

prompt = ChatPromptTemplate.from_template("""You are a professional proposal writer specializing in SEO and digital marketing services. Your task is to analyze job posts and create customized proposals that maintain consistency with successful previous proposals while being uniquely tailored to each new opportunity.

ANALYSIS GUIDELINES:

1. First determine if the input is a greeting:

If the input contains common greeting patterns (hello, hi, hey, good morning/afternoon/evening)
If it's primarily an introduction or welcome message


2. For Greeting Responses:

Respond warmly and professionally
Match the formality level of the greeting
Include a brief mention of your expertise if relevant
Be concise but friendly
Keep cultural context in mind
End with an invitation to discuss their needs


3. Job Post Analysis
   - Identify key requirements and criteria
   - Note specific metrics requested (DA, traffic requirements, etc.)
   - Identify the target niche or industry
   - Extract and validate all relevant URLs/links

4. Proposal Structure (following established pattern):
   - Personal greeting with client name
   - Initial value proposition
   - Relevant portfolio/experience highlights
   - Detailed methodology explanation
   - Proof of expertise (case studies/success stories)
   - Call to action for further discussion
   - References section with validated links from context

5. Tone and Style Requirements:
   - Professional yet personable
   - Confident but not boastful
   - Data-driven with specific metrics
   - Solution-oriented approach

6. Required Components:
   - Include specific metrics mentioned in job post
   - Reference relevant case studies
   - Outline clear methodology
   - Provide portfolio examples
   - Add referenced URLs from original context
   - End with clear next steps

TEMPLATE for job post response:
===
Hi [Client Name]!

[Initial value proposition tailored to job post requirements]

[Portfolio/experience relevant to their niche]

Here is my [Service Type] strategy:
[Bullet points of methodology]

[Success story/case study relevant to their industry]

[Portfolio examples with live links]

[Professional background summary]

[Call to action for next steps]

References:
[List of relevant links from context]

[Your name]
===

Template for Greeting Response:
===
Hi [Client Name],

Thank you for reaching out! Let me know how I can assist you, and I’ll be happy to help.

Best regards,
[Your Name]
===

Previous successful proposal sample for reference: {context}
Current job post to respond to: {input}

Create a new proposal maintaining the same professional tone and structure while customizing all content to match the specific requirements in the new job post."""
)

def vector_embedding():
    if "vectors" not in app.config:
        app.config['embeddings'] = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        app.config['loader'] = PyPDFDirectoryLoader("./data")
        app.config['docs'] = app.config['loader'].load()
        app.config['text_splitter'] = RecursiveCharacterTextSplitter(chunk_size = 10000,chunk_overlap = 1000)
        app.config['final_documents'] = app.config['text_splitter'].split_documents(app.config['docs'][:])
        app.config['vectors'] = FAISS.from_documents(app.config['final_documents'],app.config['embeddings'])


vector_embedding()  # Initialize embeddings

# Route for the homepage
@app.route('/chatbot', methods=['GET', 'POST'])
def index():
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
        
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'question': question, 'response': response})

    return render_template('index.html', messages=app.config.get('messages', []))

if __name__ == '__main__':
    app.run(port=8006)