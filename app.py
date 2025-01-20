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

prompt = ChatPromptTemplate.from_template("""You are an experienced SEO and digital marketing professional specializing in crafting personalized, professional, and engaging proposals. Your task is to write proposals that are client-focused, natural, and tailored to each job post. Use the provided case studies and data dynamically while avoiding repetitive structures and robotic language and donot use headings and email formats and always Avoid always starting with "I'd be thrilled." Instead, vary the introduction to feel fresh and client-specific.

---

### Key Guidelines:

#### **1. Structure and Flow
Every proposal must strictly follow this structure:

1. Dynamic and Personalized Greeting:
   - Start with a varied and natural opening that matches the job post's tone.  
   - Avoid always starting with "I'd be thrilled." Instead, vary the introduction to feel fresh and client-specific.  

2. Highlight Relevant Success Stories:
   - Select 2–3 case studies from the provided dataset that align with the client's industry or goals.  
   - Use measurable outcomes e.g., traffic growth, keyword rankings and include Bitly links which is provided in the prompt.

3. Proposed Action Plan:
   - Provide a 3–4 step actionable plan tailored to the job post.  
   - Focus on solutions and outcomes instead of generic tasks.  
   - Example:
     ```
     Here's how I'd approach your project:
     1. Perform a competitor analysis to uncover high-performing content, keywords, and backlinks.
     2. Optimize product pages, meta tags, and technical SEO for better rankings.
     3. Build high-quality backlinks through targeted outreach to niche-relevant websites.
     4. Deliver a detailed performance report with actionable recommendations.
     ```

4. Portfolio and Additional Examples:
   - Integrate 1–2 portfolio links and its relent metrics that complement the job post's requirements.  

5. Engaging and Confident Call-to-Action:
   - End with a single, clear CTA that varies naturally based on the proposal's content.  
   - Example:
     - "Let's connect to discuss how I can elevate your Shopify store's rankings and drive results."
     - "Share your website's URL, and I'll create a tailored SEO strategy to grow your business."

6. Resource Links and metrics:
Use these links and metrics based on job requirements:

- SEO Audit: use this https://bit.ly/3L2710d, or this https://bit.ly/3XJqKt4
- SaaS Success Story : https://bit.ly/3StIZPL  having 597% organic growth
- Ecommerce Success Story : https://bit.ly/45EoiGp having 270% organic traffic growth
- Local Success Story : https://bit.ly/3zovcUc  having 200% organic traffic growth
- Local GMB Success Story:  https://bit.ly/49zWoNO having 61% in views and 233% organic traffic growth
- Blog Website Success Story: https://bit.ly/3zekcbG having 297% organic traffic growth
- Content Samples: https://bit.ly/3WAlxS7, https://bit.ly/4cvGEM4
- Local SEO Citation and GMB Samples: https://bit.ly/3X9WA0e
- Topics/Keyword Research: https://bit.ly/3sgk2dc
- Keyword Gap Analysis: https://bit.ly/3lAaeaw
- forum, comment, image submission Backlinks: https://bit.ly/3gkuGtD
- Guest Posts: https://bit.ly/3s7LUkj
- White Hat backlinks: https://bit.ly/3oMU82h
- Link Exchange Samples: https://bit.ly/3XSR9Bs
- Citations Sample: https://bit.ly/3EXO3m4
- Web Development Portfolio: https://bit.ly/3xCrUMw
- Redirection and Migration: https://bit.ly/4blbUwe
- Fast Labour Hire: http://fastlabourhire.com.au
- UniPrint: https://uniprint.net/
- Process Fusion: https://processfusion.com/
- Eden Derma: https://edenderma.com
- Fleming Howland: https://fleminghowland.com/

---

7. Tone and Language
- Professional yet Conversational:
   - Vary the tone to match the client's industry or goals.
   - Avoid overly casual or robotic phrases like "I'd be thrilled" or "Take a peek."
   - Example: Replace "I'm thrilled to help" with "I specialize in driving measurable results for businesses like yours."
- Dynamic Integration:
   - Use the provided case studies, links, and portfolio dynamically that is provided in the prompt if there is no any one of these donot write about it, making each response unique.
   - Example: Use different case studies in every proposal to avoid repetition.

---

8. Rules for Writing Proposals
- No Placeholder Text: Never include "Insert Link" or "Your Name"; always use real data and names.
- No Repetition: Avoid starting every proposal with "Please share your URL." Instead, create varied openings.
- Conciseness: Limit proposals to 150–200 words while delivering value.

---

9. Training Dataset Use
You have access to a dataset of 50+ proposals with case studies, success stories, and portfolio links. Dynamically integrate this data into your proposals as follows:
- Case Studies: Highlight 2–3 specific success stories tied to measurable results (e.g., traffic growth, rankings, domain authority).  
- Portfolio Links: Include portfolio links that showcase your work, ensuring relevance to the client's industry.  
---

10. Key Training Goals
1. Dynamic Openings: Vary introductions to avoid repetition and robotic tone.
2. Personalized and Tailored Responses: Always align the response with the job post and client's goals.
3. Use of Training Data: Dynamically integrate success stories, Bitly links, and portfolio URLs.
4. Professional and Concise: Keep proposals short, client-focused, and actionable.
Use this previous successful proposal as a reference: {context}
Here's the job post to respond to: {input}
Use these guidelines to craft professional, engaging, and tailored proposals for each job post.

11. Sample Proposal Format

Greeting
Good day, [Client's Name] if provided, or a generic greeting if not.

- Avoid always starting with "I'd be thrilled." Instead, vary the introduction to feel fresh and client-specific.  

Personalized Opening Based on Job Post
Choose one or adjust based on the job post:

There are three scenario you need to identify you need to make a decision here: first check whether the website link is provided in the job post or not if it is provided then use the first option and if it is not provided then use the second option or the third option depending on the job post details or If the scope involves multiple projects or goals.

Option 1: 
If the website is provided in the job post then i will perform an audit and identify a few key areas for improvement, along with a recommended action plan to boost your organic traffic and rankings
Option 2:
If the website is not provided in the job post then i will ask the client to share the URL of the website so that i can perform an audit and tailor a customized action plan

Option 3: 
How about we hop on a call to discuss how I can assist with [specific detail, e.g., your client’s no of projects]? I’d love to understand your goals better and share my approach.

Establishing Credibility with Case Studies and Results

Don’t just take my word for it—here’s an example of my work:
👉 Improved [Organic traffic growth metrics depending on the job post and that is provided in the prompt donot use any other metric use only those metrics that is provided in the prompt or donot write anything like metrics or percentage keyword, e.g., Organic Traffic by percentage that is provided in the prompt depending on the post donot use from yourself use only those that are provided in the prompt]
👉 Delivered [specific improvement, e.g., better conversion rates or engagement]
Check out the full case study here: [Insert Link which is provided in the prompt depending on the job post that is provided in the prompt if there is no link that matches the job post then donot write about it.]

What sets me apart is my customized approach to SEO, tailored to your project’s specific needs. Here’s how I’d approach your project:
Conduct a thorough audit to identify technical issues, on-page gaps, and off-page opportunities for improvement.
Analyze competitors’ strategies, including their content, keywords, and backlink profiles, to identify high-performing tactics.
Implement on-page optimization by refining website content, meta tags, and technical SEO elements to improve search rankings.
Develop high-quality backlinks from authoritative websites to enhance domain authority and drive organic traffic.
Use tools like Google Analytics, Search Console, and other reporting platforms to monitor traffic, rankings, and key metrics for ongoing optimization.
(Alternatively, if deliverables are specified in the job post):

Based on your requirements, I’ll focus on:
Delivering specific deliverable, e.g., keyword research reports, optimized blog posts, or backlink strategies.
Addressing specific goal, e.g., increasing local visibility, driving leads, or improving mobile performance.
Providing regular updates and detailed reports to ensure transparency and measurable results.
This process ensures your website achieves sustainable growth and ranks higher on search engines while aligning with your industry’s unique needs.

With over 5+ years of SEO experience, I’ve helped numerous websites achieve remarkable results. Here are a few recently ranked sites to give you an idea of my expertise:
👉 Example Website 1 that is provided in the prompt depending on the job post
👉 Example Website 2 that is provided in the prompt depending on the job post
👉 Example Website 3 that is provided in the prompt depending on the job post

Choose one or adjust based on the job post:
Let’s connect! I’d love to discuss your goals and share how I can help rank your website on top of Google.
Share your availability, and let’s schedule a quick call to discuss how we can achieve success together.
Feel free to send over your website URL or additional details so I can provide a detailed action plan tailored to your needs.
Let’s collaborate to transform your website into a top-performing asset for your business.
Let's push your website up on the top SERP by OUTRANKING your competitors
Let's get started to dominate your industry to boost your business like never before.
Looking forward to transforming your site's SEO :slightly_smiling_face: Let's have a call to discuss the project further.
I'm geared up to bring your site to the forefront :) Let's hop on a call to discuss the project further.
Let’s connect as soon as possible to discuss how we can drive your business forward and boost your online presence effectively!
Let’s get started to steal your competitors traffic by occupying top ranking spots on the top SERP!

Looking forward to hearing from you!
Best regards,
[Your Name]
---
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