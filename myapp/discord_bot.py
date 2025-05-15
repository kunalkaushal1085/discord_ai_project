import logging,requests,json,telegram,pinecone
from time import sleep
from telegram import Update
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings as mainEmbed
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters)
import tracemalloc
from langchain.vectorstores import Pinecone
from django.conf import settings
import os,time
import asyncio
import requests
# from bardapi import Bard
# import bardapi
import os
import discord
from discord.ext import commands
from requests.exceptions import ReadTimeout
from retrying import retry
from dotenv import load_dotenv
from langchain.memory import ConversationBufferMemory
import openai
from openai.embeddings_utils import get_embedding
import re

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(command_prefix="$", intents=intents)

tracemalloc.start()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


pinecone_key = os.getenv("pinecone_key_discord")
api_key = os.getenv("OPENAI_API_KEY")
pinecone_env = "gcp-starter"
embeddings_model = mainEmbed(model='text-embedding-ada-002',openai_api_key=api_key)
index_name = "document"
pinecone.init(api_key = pinecone_key, environment = pinecone_env)
vector_store = Pinecone.from_existing_index(index_name,embeddings_model)


file_path = '/var/www/html/captain_admin/myapp/data/promptDiscord.txt'

with open(file_path, 'r') as file:
    context = file.read()


prompt_template = context

chat_history=[]


PROMPT = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)


chain_type_kwargs = {"prompt": PROMPT}



def answer(vector_store,query):
    llm = ChatOpenAI(model='gpt-3.5-turbo', temperature=0.2,openai_api_key=api_key)
    retreiver = vector_store.as_retriever(search_type='similarity',search_kwargs={'k':2})

    print("AFTER CHAIN", chain_type_kwargs)
    chain = RetrievalQA.from_chain_type(llm=llm,
                                 chain_type="stuff",
                                 retriever=retreiver,
                                 chain_type_kwargs=chain_type_kwargs)

    ans = chain.run(query)
    return ans


@client.event
async def on_ready():
    print(f'The bot is ready for use!')
    print('--------------------------')


discord_token = os.getenv('Discord_Token')

@retry(
    retry_on_exception=lambda exc: isinstance(exc, ReadTimeout),
    wait_exponential_multiplier=1000,  # Wait for 1 second, then 2 seconds, 4 seconds, etc.
    stop_max_attempt_number=3,  # Maximum of 3 retries
)


#get chat history from discord
async def get_chat_history_as_string(message,author):
    chat_history=[]
    author=str(author)
    try:
        limit = 20
        get_history = message.channel.history(limit=limit, oldest_first=False)
        print("GET", get_history)
        chat_string = ""
        chat_list = []
        async for msg in get_history:
            if True:
                if msg.author.name == 'Ticket Tool':
                    continue

                chat_list.append(f"{msg.content}\n\n")

        if len(chat_list) > 0:

            chat_list.reverse()
            for chat in chat_list:
                chat_string += chat

        return chat_string
    except Exception as e:
        await message.channel.send("There is some problem please try again!!!")


# fetch the relevant response from the pinecon
def response_from_pinecon(my_inp,index):
    openai.api_key=api_key
    my_inp_embed = get_embedding(my_inp, engine="text-embedding-ada-002")

    index = pinecone.Index(index)

    res = index.query(
        vector = my_inp_embed,
        top_k = 3,
        include_metadata =True,
        include_values = False
    )

    context = ''
    for i in res['matches']:
        context += i['metadata']['text'] + '\n'

    return context

# get the response from  openai
def history(context=None, vector_store=vector_store, discord_messages=None, discord_query=None):

    openai.api_key=api_key
    response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Data: {}\n\n {}You will answer according to provided data.".format(context, vector_store)},
    {"role": "system", "content": "Okay got it."},
    {"role": "user", "content": "here we have the previous conversation, so also response on the behalf of previous conversation:\n\n{}".format(discord_messages)},
    {"role": "system", "content": "Ok I'll remember this, now share me your query."},
    {"role": "user", "content": "Here is my query:\n{}".format(discord_query)}
    ]
    )

    response_sent = response['choices'][0]['message']['content']
    return response_sent



@client.event
async def on_message(message):
    if message.author.bot or isinstance(message.channel, discord.DMChannel):
        return

    if message.channel.id != 1197465430932078604:
        return
    if  message.content.lower():
        content = message.content.lower()
        if content:
                await message.channel.typing()

                vector_store = Pinecone.from_existing_index(index_name,embeddings_model)
                async with message.channel.typing():
                    string_history =  await get_chat_history_as_string(message,message.author)
                    await message.channel.typing()

                    vector_store=response_from_pinecon(content,index_name)
                    await message.channel.typing()

                    # old prompt
                    old_prompt=prompt_template.encode('utf-8').decode('utf-8')

                    # clean the prompt:
                    pattern = r'\{[^{}]*\}'
                    cleaned_prompt=re.sub(pattern, '', old_prompt)
                    search_results = history(context=cleaned_prompt, vector_store=vector_store, discord_messages=string_history, discord_query=content)
                    handle_error_messages = ["Response Error", "Unable to get response"]
                    if any(error_message in search_results for error_message in handle_error_messages):
                        search_results = ("Please wait a few minutes while I am processing your request OR try again after "
                                    "a few minutes later!!!")
                        await message.channel.send(f"1 {search_results}")
                    else:
                        if len(search_results) > 2000:
                            parts = [search_results[i:i + 2000] for i in range(0, len(search_results), 2000)]
                            for part in parts:
                                await message.channel.typing()
                                await message.channel.send(part)
                        else:
                            await message.channel.typing()
                            await message.channel.send(search_results)
                await client.process_commands(message)
        else:
            await message.channel.send("No search results found.")




client.run(discord_token)
