from django.shortcuts import render,redirect
from django.conf import settings
import os
import time
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login,logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from langchain.embeddings import OpenAIEmbeddings as mainEmbed
from pinecone import Pinecone, ServerlessSpec
from langchain.vectorstores import Pinecone as LangchainPinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Pinecone as LangchainPinecone



# Create your views here
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")
discord_api_key = os.getenv("PINECONE_API_DISCORD")
pc = Pinecone(api_key=api_key)
pc1 = Pinecone(api_key=discord_api_key)
openai_api_key = os.getenv("openai_api_key")
pinecone_env = os.getenv("pinecone_env")


#Embedding model
embeddings_model = mainEmbed(model='text-embedding-ada-002',openai_api_key=openai_api_key)

index_name = "document"

def not_logged_in(user):
    return not user.is_authenticated

@login_required(login_url='login')
def index(request):
    return render(request, 'index.html')

# @user_passes_test
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('index')
        else:
            messages.error(request, 'Invalid email or password.')
    # return redirect('login')
    return render(request, 'login.html')

@login_required(login_url='login')
def prompt(request):
    # file_path = 'myapp/data/prompt.txt'
    file_path = os.path.join(settings.BASE_DIR, 'myapp/data/prompt.txt')
    if request.method == 'POST':
        new_content = request.POST.get('prompt')

        with open(file_path, 'w') as file:
            file.write(new_content)
        messages.success(request, 'Prompt updated successfully.')  # Add this line
        return redirect('prompt')

    with open(file_path, 'r') as file:
        text_content = file.read()

    context = {
        'text_content': text_content,
    }
    return render(request, 'prompt.html', context)

#Telegram Bot
@login_required(login_url='login')
def data(request):
    file_path = os.path.join(settings.BASE_DIR, 'myapp/data/mainData.txt')
    if request.method == 'POST':
        delete_index()
        new_content = request.POST.get('data')
        with open(file_path, 'w') as file:
            file.write(new_content)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size = 256,
            chunk_overlap  = 0,
            length_function = len,
            add_start_index = True,
        )
        chunks = text_splitter.create_documents([new_content])
        create_index(index_name,chunks)


        messages.success(request, 'Data Trained successfully.')
        return redirect('data')

    with open(file_path, 'r') as file:
        text_content = file.read()

    context = {
        'text_content': text_content,
    }
    return render(request, 'data.html', context)

# @login_required(login_url='login')
# def data(request):
#     file_path = os.path.join(settings.BASE_DIR, 'myapp/data/mainData.txt')

#     if request.method == 'POST':
#         new_content = request.POST.get('data', '')
#         if not new_content.strip():
#             messages.error(request, "Empty content provided.")
#             return redirect('data')

#         delete_index()  # This deletes all indexes — adjust if needed
#         with open(file_path, 'w') as file:
#             file.write(new_content)

#         # Chunk text
#         text_splitter = RecursiveCharacterTextSplitter(
#             chunk_size=256,
#             chunk_overlap=0,
#             length_function=len,
#             add_start_index=True,
#         )
#         chunks = text_splitter.create_documents([new_content])
#         create_index(index_name, chunks)

#         messages.success(request, 'Data Trained successfully.')
#         return redirect('data')

#     with open(file_path, 'r') as file:
#         text_content = file.read()

#     context = {'text_content': text_content}
#     return render(request, 'data.html', context)


@login_required(login_url='login')
def logout_view(request):
    logout(request)
    return redirect('login')

# Discord Bot
@login_required(login_url='login')
def promptDiscord(request):
    print(settings.BASE_DIR, "BASE__DIR")
    file_path = os.path.join(settings.BASE_DIR, 'myapp/data/promptDiscord.txt')
    # file_path = "'./data/promptDiscord.txt"
    if request.method == 'POST':
        new_content = request.POST.get('prompt')
        print(new_content,"???????")
        with open(file_path, 'w') as file:
            file.write(new_content)
        messages.success(request, 'Prompt updated successfully.')  # Add this line
        return redirect('promptDiscord')

    with open(file_path, 'r') as file:
        text_content = file.read()

    context = {
        'text_content': text_content,
    }
    return render(request, 'promptDiscord.html',context)


@login_required(login_url='login')
def dataDiscord(request):

    file_path = os.path.join(settings.BASE_DIR, 'myapp/data/dataDiscord.txt')
    if request.method == 'POST':
        new_content = request.POST.get('data')
        print(new_content,">>>>>>")

        with open(file_path, 'w') as file:
            file.write(new_content)
        delete_index_discord()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size = 256,
            chunk_overlap  = 0,
            length_function = len,
            add_start_index = True,
        )
        print(new_content)
        chunks = text_splitter.create_documents([new_content])
        create_index_discord(index_name,chunks)
        messages.success(request, 'Data updated successfully.')
        return redirect('dataDiscord')

    with open(file_path, 'r') as file:
        text_content = file.read()

    context = {
        'text_content': text_content,
    }

    return render(request, 'dataDiscord.html',context)

def create_index(index_name, chunks):
    print(f"{index_name=}")
    # Create index if it does not exist
    if index_name not in pc.list_indexes().names():
        pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )

    # ✅ Get the Index object
    index = pc.Index(index_name)
    try:
        index.describe()
        print("Index exists and is accessible")
    except Exception as e:
        print(f"Error accessing index: {e}")
    # ✅ Correct way to use Langchain's Pinecone integration (v3)
    try:
        vectorstore = LangchainPinecone.from_documents(
        documents=chunks,
        embedding=embeddings_model,
        index=index, # Pass the actual Index object
        namespace=None
        )
        return vectorstore
    except Exception as e:
        print(f"Error creating vectorstore: {e}")


def delete_index(index_name="all"):
    if index_name == "all":
        print("Deleting All indexes...")
        for idx in pc.list_indexes().names():
            pc.delete_index(idx)
        print("Deleted all indexes.")
    else:
        pc.delete_index(index_name)
        print(f"Deleted index: {index_name}")


def create_index_discord(index_name, chunks):

    # Create index if it does not exist
    if index_name not in pc1.list_indexes().names():
        pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )

    # ✅ Get the Index object
    index = pc1.Index(index_name)
    try:
        index.describe()
        print("Index exists and is accessible")
    except Exception as e:
        print(f"Error accessing index: {e}")
    # ✅ Correct way to use Langchain's Pinecone integration (v3)
    try:
        vectorstore = LangchainPinecone.from_documents(
        documents=chunks,
        embedding=embeddings_model,
        index=index, # Pass the actual Index object
        namespace=None
        )
        return vectorstore
    except Exception as e:
        print(f"Error creating vectorstore: {e}")


def delete_index_discord(index_name="all"):

    if index_name == "all":
        print("Deleting All indexes...")
        for idx in pc1.list_indexes().names():
            pc.delete_index(idx)
            print("Deleted all indexes.")
    else:
        pc.delete_index(index_name)
        print(f"Deleted index: {index_name}")


