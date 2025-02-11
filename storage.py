import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import requests

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
import mimetypes

load_dotenv()

azureStorage_url = os.getenv("account_url")
credential = DefaultAzureCredential()

blob_service_client = BlobServiceClient(azureStorage_url, credential=credential)

if blob_service_client:
    print("BlobServiceClient created successfully.")


# try:
#     containers = blob_service_client.list_containers()
#     for container in containers:
#         print(container.name)
#     print("Azure Storage에 성공적으로 연결되었습니다.")
# except Exception as e:
#     print(f"연결 중 오류 발생: {str(e)}")

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
def upload_image_to_blob(blob_service_client: BlobServiceClient, container_name: str, image_path: str, blob_name: str):
    container_client = blob_service_client.get_container_client(container=container_name)
    with open(file=image_path, mode="rb") as image_file:
        blob_client = container_client.upload_blob(name=blob_name, data=image_file, overwrite=True)

    print(f"이미지 '{blob_name}'가 '{container_name}' 컨테이너에 업로드되었습니다.")
    return blob_client.url

def upload_imgFile_to_blob(blob_service_client: BlobServiceClient, container_name, file_data, blob_name):
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    
    # MIME 타입 설정 (예: image/png)
    content_type = get_content_type(blob_name)
    content_settings = ContentSettings(content_type=content_type)
    blob_client.upload_blob(file_data, overwrite=True,content_settings=content_settings)
    return blob_client.url


def upload_image_to_blob_with_url(blob_service_client: BlobServiceClient, container_name: str, image_url: str,
                                  blob_name: str):
    container_client = blob_service_client.get_container_client(container=container_name)
    image_file = requests.get(image_url).content
    blob_client = container_client.upload_blob(name=blob_name, data=image_file, overwrite=True)

    print(f"이미지 '{blob_name}'가 '{container_name}' 컨테이너에 업로드되었습니다.")
    return blob_client.url


def delete_blob_by_url(blob_service_client: BlobServiceClient, container_name: str, blob_url):
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

# delete_blob_by_url(blob_service_client, 'img','https://bonlestorage.blob.core.windows.net/img/product/brand_hd/bu.jpg')