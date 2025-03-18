import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import requests

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
import mimetypes

load_dotenv()

def get_blob_service_client():
    azureStorage_url = os.getenv("azure_storage_url")
    if not azureStorage_url or not isinstance(azureStorage_url, str):
        raise ValueError("azure_storage_url 환경 변수가 설정되지 않았거나 유효하지 않습니다.")
    
    credential = DefaultAzureCredential()
    return BlobServiceClient(azureStorage_url, credential=credential)

def get_content_type(filename):
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        return mime_type
    # 파일 확장자별로 MIME 타입 지정
    ext = filename.lower().split('.')[-1]
    if ext in ['jpg', 'jpeg']:
        return 'image/jpeg'
    elif ext == 'png':
        return 'image/png'
    else:
        return 'application/octet-stream'  # 기본값

# image_path : 이미지 경로 , blob_name : blob에 저장될 이름
def upload_image_to_blob(container_name: str, image_path: str, blob_name: str):
    blob_service_client = get_blob_service_client()
    container_client = blob_service_client.get_container_client(container=container_name)
    with open(file=image_path, mode="rb") as image_file:
        blob_client = container_client.upload_blob(name=blob_name, data=image_file, overwrite=True)

    print(f"이미지 '{blob_name}'가 '{container_name}' 컨테이너에 업로드되었습니다.")
    return blob_client.url

def upload_imgFile_to_blob(container_name, file_data, blob_name):
    blob_service_client = get_blob_service_client()
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    
    # MIME 타입 설정 (예: image/png)
    content_type = get_content_type(blob_name)
    content_settings = ContentSettings(content_type=content_type)
    try:
        blob_client.upload_blob(file_data, overwrite=True,content_settings=content_settings)
    except Exception as e:
        print(f"Blob 업로드 중 오류 발생: {str(e)}")
        return None
    return blob_client.url

def upload_image_to_blob_with_url(container_name: str, image_url: str, blob_name: str):
    blob_service_client = get_blob_service_client()
    container_client = blob_service_client.get_container_client(container=container_name)
    image_file = requests.get(image_url).content
    blob_client = container_client.upload_blob(name=blob_name, data=image_file, overwrite=True)

    print(f"이미지 '{blob_name}'가 '{container_name}' 컨테이너에 업로드되었습니다.")
    return blob_client.url

def delete_blob_by_url(container_name: str, blob_url):
    blob_service_client = get_blob_service_client()
    container_client = blob_service_client.get_container_client(container=container_name)

    parsed_url = urlparse(blob_url)
    container_name = parsed_url.path.split('/')[1]
    blob_name = '/'.join(parsed_url.path.split('/')[2:])

    # BlobClient 생성
    try:
        blob_client = container_client.delete_blob(blob_name, delete_snapshots="include")
        print(f"Blob '{blob_name}' 삭제 완료")
        return True
    except Exception as e:
        print(f"Blob 삭제 중 오류 발생: {str(e)}")
        return False
