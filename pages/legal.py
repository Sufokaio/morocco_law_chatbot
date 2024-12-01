

import os
import glob
from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

from openai import OpenAI

import subprocess;
from google.cloud import translate_v2 as translate
import streamlit as st



load_dotenv()
os.environ['OPENAI_API_KEY'] = st.secrets["OPENAI_API_KEY"]

embeddings = OpenAIEmbeddings()
specialities = ["travail",  "commerce", "contrats"]

def save_faiss_index(speciality):
    with open("data/" + speciality + ".txt", "r", encoding="utf-8-sig") as file:
        data = file.read()
    text_splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=200)
    chunks = text_splitter.split_text(data)
    faiss_index = FAISS.from_texts(chunks, embeddings)
    faiss_index.save_local( speciality + "_index")

for speciality in specialities:
    save_faiss_index(speciality)

travail_index = FAISS.load_local("travail" + "_index", embeddings, allow_dangerous_deserialization= True)
commerce_index = FAISS.load_local("commerce" + "_index", embeddings, allow_dangerous_deserialization= True)
contrats_index = FAISS.load_local("contrats" + "_index", embeddings, allow_dangerous_deserialization= True)



class Chatbot:

    def translate_text(self, text, target_lang):
        client = translate.Client.from_service_account_json("data/Google_KEY.json")
        result = client.translate(text, target_language=target_lang)
        return result['translatedText']
    
    openai = OpenAI()

    def __init__(self):
        print("Starting the chatbot")

    def generate_answer(self, query: str, speciality: str, system_prompt):
        if(speciality == "travail"):
            index = travail_index
        elif(speciality == "commerce"):
            index = commerce_index
        else:
            index = contrats_index

        results = index.similarity_search(query, k=3)            
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
        system_prompt = "tu dois me dire si la phrase donnée est en marocain ou en français. ne répond qu'avec 'fraçais' ou 'arabe' et aucun autre mot"
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
            
