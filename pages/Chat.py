import json
import streamlit as st
import requests




import os
import glob
from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

from openai import OpenAI

import subprocess;
from google.cloud import translate_v2 as translate


import os
import streamlit as st





load_dotenv()
os.environ['OPENAI_API_KEY'] = st.secrets["OPENAI_API_KEY"]

embeddings = OpenAIEmbeddings()
specialities = ["travail",  "commerce", "contrats"]

def save_faiss_index(speciality):
    pages_dir = os.path.join(os.getcwd(), 'pages')

    file_path = os.path.join(pages_dir, speciality +'.txt')
    with open(file_path, "r", encoding="utf-8-sig") as file:
        data = file.read()
    text_splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=200)
    chunks = text_splitter.split_text(data)
    faiss_index = FAISS.from_texts(chunks, embeddings)
    faiss_index.save_local( speciality + "_index")

#for speciality in specialities:
 #   save_faiss_index(speciality)

travail_index = FAISS.load_local("travail" + "_index", embeddings, allow_dangerous_deserialization= True)
commerce_index = FAISS.load_local("commerce" + "_index", embeddings, allow_dangerous_deserialization= True)
contrats_index = FAISS.load_local("contrats" + "_index", embeddings, allow_dangerous_deserialization= True)




class Chatbot:

    def translate_text(self, text, target_lang):    
        google_cloud_secrets = st.secrets["google_cloud"]
        
        # Create a dictionary from the secrets
        credentials = {
            "type": google_cloud_secrets["type"],
            "project_id": google_cloud_secrets["project_id"],
            "private_key_id": google_cloud_secrets["private_key_id"],
            "private_key": google_cloud_secrets["private_key"],
            "client_email": google_cloud_secrets["client_email"],
            "client_id": google_cloud_secrets["client_id"],
            "auth_uri": google_cloud_secrets["auth_uri"],
            "token_uri": google_cloud_secrets["token_uri"],
            "auth_provider_x509_cert_url": google_cloud_secrets["auth_provider_x509_cert_url"],
            "client_x509_cert_url": google_cloud_secrets["client_x509_cert_url"]
        }

        # Convert the dictionary to a json string
        credentials_json = json.dumps(credentials)
        
        # Use the credentials to authenticate with Google Cloud Translate
        client = translate.Client.from_service_account_info(json.loads(credentials_json))
        
        # Translate the text
        result = client.translate(text, target_language=target_lang)
        return result['translatedText']
    
    openai = OpenAI()

    def generate_query_variations(self, query, model="gpt-4"):
        system_prompt = (
            "Tu es un assistant qui génère plusieurs variantes de requêtes pour améliorer les résultats de recherche. "
            "Garde le sens original de la question, mais reformule de manière claire et précise. "
            "Renvoie les variantes sous forme de liste séparée par des sauts de ligne."
        )
        user_prompt = f"Voici la question de l'utilisateur : {query}\nGénère 5 variantes."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = self.openai.chat.completions.create(
            model = "gpt-4o",
            messages = messages
        )
        variations = response.choices[0].message.content.strip().split("\n")
        return variations

    def __init__(self):
        print("Starting the chatbot")

    def generate_answer(self, query: str, speciality: str, system_prompt):
        if(speciality == "travail"):
            index = travail_index
        elif(speciality == "commerce"):
            index = commerce_index
        else:
            index = contrats_index

        query_variations = self.generate_query_variations(query)

        all_results = []

        for variation in query_variations:
            results = index.similarity_search(variation, k=3)  
            all_results.extend(results)

        unique_results = {result.page_content for result in all_results}
        sources_list = list(unique_results)[:4]


        sources_list = [result.page_content for result in results]
        user_prompt = f"Voici la question de l'utilisateur sur le droit du travail: {query}\nvoici les sources que tu dois utiliser pour répondre a cette question: {sources_list}"

        messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        response = self.openai.chat.completions.create(
                    model = "gpt-4o",
                    messages = messages
                )
        
        return {"answer": response.choices[0].message.content,  
                "sources": "\n\n".join(sources_list)}



    def get_answer(self, query: str, speciality: str) -> str:
        system_prompt = "tu dois me dire si la phrase donnée est en arabe ou en français. ne répond qu'avec 'français' ou 'arabe' et aucun autre mot"
        user_prompt = f"Voici la phrase que tu dois classifier: {query}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response_fr_or_ar = self.openai.chat.completions.create(model = "gpt-4o",messages = messages)
        query_language = response_fr_or_ar.choices[0].message.content

        if query_language == "arabe":
            french_query = self.translate_text(query, "ar")
            system_prompt = "Tu es un chatbot assistant conseiller juridique spécialisé en droit du travail marocain. Réponds uniquement sur la base des sources fournies. Si tu ne sais pas ou si les sources ne répondent pas à la question, dis simplement 'Je ne sais pas'. Réponds en arabe."# A la fin de t'as réponses te réécris les soucres données mots pour mots de façon exacte traduites en arabe"
            response = self.generate_answer(french_query, speciality, system_prompt)
            return response["answer"] + \
                    "\nالموارد المستخدمة هي أدناه:\n \n" + \
                    self.translate_text(response["sources"],"ar")

        else: 
            system_prompt = "Tu es un chatbot assistant conseiller juridique spécialisé en droit du travail marocain. Réponds uniquement sur la base des sources fournies. Si tu ne sais pas ou si les sources ne répondent pas à la question, dis simplement 'Je ne sais pas'."
            response = self.generate_answer(query, speciality, system_prompt)
            return response["answer"] + \
                  "\nLes resources utilisée ce trouvent ci-dessous:\n \n" + \
                   response["sources"]
            

chatbot = Chatbot()


#maybe
if 'messages' not in st.session_state:
    st.session_state['messages'] = []  

st.markdown(
    """
    <style>
    div[data-testid="stAppViewContainer"] {
        background-color: #F5F7F8;
    }

    section[data-testid="stSidebar"] > div:first-child {
        background-color: #302d34 !important; /* Sidebar background color preserved */
    }

    section[data-testid="stSidebar"] * {
        color: #ffffff !important; /* White text in the sidebar */
    }

    .icon-text {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
        padding: 10px;
        border-radius: 8px;
        transition: background-color 0.3s ease, transform 0.3s ease;
    }

    .icon-text:hover {
        background-color: #444444; /* Background color on hover */
        transform: scale(1.05); /* Zoom effect on hover */
    }

    .icon-text img {
        width: 24px;
        height: 24px;
        margin-right: 8px;
        transition: transform 0.3s ease;
    }

    .icon-text:hover img {
        transform: rotate(15deg); /* Rotation effect on hover */
    }

    .chat-bubble {
        padding: 10px 15px;
        border-radius: 20px;
        margin: 10px 0;
        max-width: 70%;
        word-wrap: break-word;
        display: inline-block;
        transition: transform 0.2s;
    }

    .user-bubble {
        background-color: #007BFF; /* User bubble color */
        color: white;
        text-align: right;
        margin-left: auto;
    }

    .bot-bubble {
        background-color: #E0E0E0; /* Bot bubble color */
        color: black;
        text-align: left;
        margin-right: auto;
    }

    .custom-button {
        padding: 12px 25px;
        font-size: 18px;
        font-weight: bold;
        color: white;
        background: linear-gradient(135deg, #FFD700, #DAA520); /* Gold gradient */
        border: none;
        border-radius: 50px;
        cursor: pointer;
        transition: all 0.3s ease;
        text-align: center;
    }

    .custom-button:hover {
        background: linear-gradient(135deg, #DAA520, #B8860B); /* Darker gold on hover */
        transform: scale(1.05); /* Slight zoom on hover */
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.sidebar.image(
    "assets/Ahmed_xy.png",
     width=300,
     use_container_width=False
)

st.sidebar.markdown(
    """
    <div style="text-align: center; font-weight: bold; font-size: 30px; margin-top: 10px;">
        Découvrez votre Bot Juridique
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown("### Choisissez la spécialité du bot :")

speciality = st.sidebar.selectbox(
    "",
    ["commerce", "travail", "contrats"]
)

st.sidebar.markdown(
    """
    <div class="icon-text">
        <img src="https://cdn-icons-png.flaticon.com/512/11746/11746496.png" alt="Icône Commerce"> 
        <span><b>Commerce</b> : Expertise en droit du commerce.</span>
    </div>
    <div class="icon-text">
        <img src="https://cdn-icons-png.flaticon.com/512/3135/3135715.png" alt="Icône Travail">
        <span><b>Travail</b> : Expertise en droit du travail.</span>
    </div>
    <div class="icon-text">
        <img src="https://cdn-icons-png.flaticon.com/512/4334/4334426.png" alt="Icône Contrats">
        <span><b>Contrats</b> : Expertise en droit des contrats et des obligations.</span>
    </div>
    """,
    unsafe_allow_html=True
)



bot_names = {
    "commerce": "Ahmy - Le Bot Commerce 🤝",
    "travail": "Youssy - Le Bot Travail 💼",
    "contrats": "Samy - Le Bot Contrat ✍️"
}

bot_title = bot_names[speciality]

st.title(bot_title)

user_input = st.text_input("Posez votre question :", key="input")

# if st.markdown(
#     """
#     <button class="custom-button">Envoyer</button>
#     """,
#     unsafe_allow_html=True
# ):
if st.button("Envoyer", key="send_button") and user_input:
    # response = requests.post(
    #     "http://localhost:8000/api/chat", 
    #     json={"question": user_input, "speciality": speciality}
    # )
    
    # if response.status_code == 200:
    #     bot_response = response.json().get("answer")
    
    # else:
    #     bot_response = "Je suis désolé, une erreur s'est produite."

    response = chatbot.get_answer(user_input, speciality)

    if response:
        bot_response = response
    
    else:
        bot_response = "Je suis désolé, une erreur s'est produite."

    st.markdown(
        f"""
        <div class="chat-bubble bot-bubble">{bot_response}</div>
        """,
        unsafe_allow_html=True
    )








