import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
import requests

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
    
    
# image_path : 이미지 경로 , blob_name : blob에 저장될 이름
def upload_image_to_blob(blob_service_client: BlobServiceClient, container_name: str, image_path: str, blob_name: str):
    container_client = blob_service_client.get_container_client(container=container_name)
    with open(file=image_path, mode="rb") as image_file:
        blob_client = container_client.upload_blob(name=blob_name, data=image_file, overwrite=True)
    
    print(f"이미지 '{blob_name}'가 '{container_name}' 컨테이너에 업로드되었습니다.")
    return blob_client.url

def upload_image_to_blob_with_url(blob_service_client: BlobServiceClient, container_name: str, image_url: str, blob_name: str):
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
