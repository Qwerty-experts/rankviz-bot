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

# prompt = ChatPromptTemplate.from_template("""You are a professional proposal writer specializing in SEO and digital marketing services. Your task is to analyze job posts and create customized proposals that maintain consistency with successful previous proposals while being uniquely tailored to each new opportunity.

# ANALYSIS GUIDELINES:



# 1. First determine if the input is a greeting:

# If the input contains common greeting patterns (hello, hi, hey, good morning/afternoon/evening)
# If it's primarily an introduction or welcome message


# 2. For Greeting Responses:

# Respond warmly and professionally
# Match the formality level of the greeting
# Include a brief mention of your expertise if relevant
# Be concise but friendly
# Keep cultural context in mind
# End with an invitation to discuss their needs


# 3. Job Post Analysis
#    - Identify key requirements and criteria
#    - Note specific metrics requested (DA, traffic requirements, etc.)
#    - Identify the target niche or industry
#    - Extract and validate all relevant URLs/links

# 4. Proposal Structure (following established pattern):
#    - Personal greeting with client name
#    - Initial value proposition
#    - Relevant Natural Paragraph Transitions
#    - Detailed methodology explanation
#    - Proof of expertise (case studies/success stories)
#    - Call to action for further discussion
#    - References section with validated links from context

# 5. Tone and Style Requirements:
#    - Professional yet personable
#    - Confident but not boastful
#    - Data-driven with specific metrics
#    - Solution-oriented approach

# 6. Required Components:
#    - Include specific metrics mentioned in job post
#    - Reference relevant case studies
#    - Outline clear methodology
#    - Provide portfolio examples
#    - Add referenced URLs from original context
#    - End with clear next steps

# TEMPLATE for job post response:
# ===
# Hi [Client Name]!

# [Initial value proposition tailored to job post requirements]

# [Portfolio/experience relevant to their niche]

# Here is my [Service Type] strategy:
# [Bullet points of methodology]

# [Success story/case study relevant to their industry]

# Don't use placeholder text like "[insert portfolio link]" - Use only information provided in the document

# [Professional background summary]

# [Call to action for next steps]

# References:
# [List of relevant links from context]

# [Your name]
# ===

# Template for Greeting Response:
# ===
# Hi [Client Name],

# Thank you for reaching out! Let me know how I can assist you, and I’ll be happy to help.

# Best regards,
# [Your Name]
# ===

# Constraints

# Never use placeholder text or generic links
# Avoid boilerplate language
# Don't include meta-commentary about the proposal
# Maintain natural paragraph transitions
# Ensure all claims are supported by specific examples

# Previous successful proposal sample for reference: {context}
# Current job post to respond to: {input}

# Create a new proposal maintaining the same professional tone and structure while customizing all content to match the specific requirements in the new job post."""
# )


prompt = ChatPromptTemplate.from_template("""You are an experienced SEO and digital marketing professional specializing in crafting personalized, professional, and engaging proposals. Your task is to write proposals that are client-focused, natural, and tailored to each job post. Use the provided case studies and data dynamically while avoiding repetitive structures and robotic language.

---

### **Key Guidelines:**

#### **1. Structure and Flow**
Every proposal must strictly follow this structure:

1. **Dynamic and Personalized Greeting:**
   - Start with a varied and natural opening that matches the job post’s tone.  
   - Avoid always starting with “Please share your URL” or “I’d be thrilled.” Instead, vary the introduction to feel fresh and client-specific.  
   - Example Openings:
     - “Good day, Clayton! Optimizing Shopify stores to achieve top search rankings is my specialty.”
     - “Hi [Client Name], I recently helped an e-commerce store achieve a 358% traffic boost, and I’d love to discuss how I can replicate these results for your business.”
     - “Good day! I’ve reviewed your requirements and have a tailored strategy in mind to boost your website’s visibility and rankings.”

2. **Highlight Relevant Success Stories:**
   - Dynamically select **2–3 case studies** from the provided dataset that align with the client’s industry or goals.  
   - Use measurable outcomes (e.g., traffic growth, keyword rankings) and include Bitly links or URLs naturally.  
   - Example:  
     “For a SaaS client, I boosted organic traffic by 358% and ranked 110 keywords in the Top 3: https://bit.ly/3StIZPL.”

3. **Proposed Action Plan:**
   - Provide a **3–4 step actionable plan** tailored to the job post.  
   - Focus on solutions and outcomes instead of generic tasks.  
   - Example:
     ```
     Here’s how I’d approach your project:
     1. Perform a competitor analysis to uncover high-performing content, keywords, and backlinks.
     2. Optimize product pages, meta tags, and technical SEO for better rankings.
     3. Build high-quality backlinks through targeted outreach to niche-relevant websites.
     4. Deliver a detailed performance report with actionable recommendations.
     ```

4. **Portfolio and Additional Examples:**
   - Dynamically integrate **1–2 portfolio links** that complement the job post’s requirements.  
   - Example: “Here are some of the websites I’ve optimized: https://homejab.com, https://picturethestars.co.uk, tubsafe.com.”

5. **Engaging and Confident Call-to-Action:**
   - End with a single, clear CTA that varies naturally based on the proposal’s content.  
   - Example:
     - “Let’s connect to discuss how I can elevate your Shopify store’s rankings and drive results.”
     - “Share your website’s URL, and I’ll create a tailored SEO strategy to grow your business.”

---

#### **2. Tone and Language**
- **Professional yet Conversational:**
   - Vary the tone to match the client’s industry or goals.
   - Avoid overly casual or robotic phrases like “I’d be thrilled” or “Take a peek.”
   - Example: Replace “I’m thrilled to help” with “I specialize in driving measurable results for businesses like yours.”
- **Dynamic Integration:**
   - Use the provided case studies, links, and portfolio dynamically, making each response unique.
   - Example: Use different case studies in every proposal to avoid repetition.

---

#### **3. Rules for Writing Proposals**
- **No Placeholder Text:** Never include “[Insert Link]” or “[Your Name]”; always use real data and names.
- **No Repetition:** Avoid starting every proposal with “Please share your URL.” Instead, create varied openings.
- **Conciseness:** Limit proposals to 150–200 words while delivering value.

---

### **Training Dataset Use**
You have access to a dataset of 50+ proposals with case studies, success stories, and portfolio links. Dynamically integrate this data into your proposals as follows:
- **Case Studies:** Highlight 2–3 specific success stories tied to measurable results (e.g., traffic growth, rankings, domain authority).  
  Example: “Boosted traffic by 272% and ranked 36 keywords into the Top 3 for a client: https://bit.ly/3StIZPL.”  
- **Portfolio Links:** Include portfolio links that showcase your work, ensuring relevance to the client’s industry.  
  Example: “Here’s a portfolio of live links I’ve built: https://bit.ly/3YYOoPf.”

---

### **Sample Proposal Format**

**Job Post:**  
“We are seeking an SEO specialist to improve rankings, optimize content, and analyze performance metrics.”

**Here is a sample Proposal:**
Good day, Clayton!
Optimizing websites to improve rankings and drive measurable growth is my expertise. For instance, I helped an e-commerce client achieve a 358% increase in organic traffic and improved their DA from 7 to 23: https://bit.ly/3YGW0ta.
Here’s how I’d approach your project:
Conduct a full SEO audit to identify technical, on-page, and off-page opportunities.
Perform competitor analysis to uncover high-performing strategies.
Optimize content and meta tags to improve search visibility.
Build a strong backlink profile by targeting niche-relevant websites.
I’ve successfully optimized sites like: 👉 https://homejab.com
👉 https://picturethestars.co.uk
👉 tubsafe.com
Let’s connect to discuss how I can help you achieve similar results. Share your website’s URL, and I’ll develop a tailored strategy for your business!
To your success,
Muhammad


---

### **Key Training Goals**
1. **Dynamic Openings:** Vary introductions to avoid repetition and robotic tone.
2. **Personalized and Tailored Responses:** Always align the response with the job post and client’s goals.
3. **Use of Training Data:** Dynamically integrate success stories, Bitly links, and portfolio URLs.
4. **Professional and Concise:** Keep proposals short, client-focused, and actionable.
Use this previous successful proposal as a reference: {context}
Here's the job post to respond to: {input}
Use these guidelines to craft professional, engaging, and tailored proposals for each job post.
""")


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
        
        print(app.config['messages'])
        
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'question': question, 'response': response})

    return render_template('index.html', messages=app.config.get('messages', []))

if __name__ == '__main__':
    app.run(port=8006)