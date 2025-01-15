import os
import sys
import json
import requests
import logging
import re
from fuse import FUSE, Operations
from collections import defaultdict
from time import time

# Set up logging
logging.basicConfig(filename=os.path.expanduser('~/fusegpt.log'), level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

class OpenAIFS(Operations):
    def __init__(self, api_key):
        self.api_key = api_key
        self.dir_cache = {}
        self.file_cache = {}
        self.cache_expiry = 300  # Cache expiry time in seconds
        logging.info('OpenAIFS initialized with API key')

    def readdir(self, path, fh):
        logging.info(f'readdir called with path: {path}')
        current_time = time()
        
        # Check if the directory listing is in the cache and not expired
        if path in self.dir_cache and current_time - self.dir_cache[path]['time'] < self.cache_expiry:
            logging.info(f'Using cached directory listing for path: {path}')
            return self.dir_cache[path]['files']
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        data = {
            'model': 'gpt-3.5-turbo',
            'messages': [{'role': 'system', 'content': f'Give me a list of files and directories, for this path: {path}, without any explanation or extra text'}],
            'max_tokens': 100
        }
        response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, data=json.dumps(data))
        logging.debug(f'Raw response from OpenAI: {response.text}')
        
        if response.status_code == 200:
            response_json = response.json()
            if 'choices' in response_json and len(response_json['choices']) > 0:
                raw_files = response_json['choices'][0]['message']['content'].strip().split('\n')
                files = [re.sub(r'^\d+\.\s*', '', file).strip() for file in raw_files]
                logging.info(f'Files received: {files}')
                self.dir_cache[path] = {'files': ['.', '..'] + files, 'time': current_time}
                return self.dir_cache[path]['files']
            else:
                logging.warning('No choices found in response')
                return ['.', '..']  # Return an empty directory if no choices are found
        else:
            logging.error(f'Failed to get response from API, status code: {response.status_code}')
            return ['.', '..']  # Return an empty directory if the request fails

    def getattr(self, path, fh=None):
        logging.info(f'getattr called with path: {path}')
        if path == '/' or path.endswith('/'):
            return dict(st_mode=(0o755 | 0o040000), st_nlink=2)
        else:
            return dict(st_mode=(0o644 | 0o100000), st_nlink=1, st_size=1024)

    def open(self, path, flags):
        logging.info(f'open called with path: {path}')
        return 0

    def read(self, path, size, offset, fh):
        # Extract file extension from path
        file_ext = os.path.splitext(path)[1]
        # extract the filename without extension and convert _ and - to space
        promptpath = os.path.splitext(path)[0].replace('_', ' ').replace('-', ' ')
        if file_ext == '.txt':
            request = f'Generate a random text file, telling me about {promptpath}, Only return the text contents, without any explanation or extra text.'
        elif file_ext == '.json':
            request = f'Generate a random JSON file, describing {promptpath}, Only return the JSON contents, without any explanation or extra text.'
        elif file_ext == '.csv':
            request = f'Generate a random CSV file, containing data for {promptpath}, Only return the CSV contents, without any explanation or extra text.'
        elif file_ext == '.html':
            request = f'Generate a random HTML file, with content for {promptpath}, Only return the HTML contents, without any explanation or extra text.'
        elif file_ext == '.py':
            request = f'Generate a random Python file, with code for {promptpath}, Only return the PY contents, without any explanation or extra text.'
        elif file_ext == '.sh':
            request = f'Generate a random shell script, with commands for {promptpath}, Only return the shell contents, without any explanation or extra text.'
        elif file_ext == '.php':
            request = f'Generate a random PHP file, with code for {promptpath}, Only return the PHP contents, without any explanation or extra text.'
        elif file_ext == '.pl':
            request = f'Generate a random perl file, with code for {promptpath}, Only return the perl contents, without any explanation or extra text.'
        else:
            request = 'Generate a random text file, telling me about {promptpath}, Only return the text contents, without any explanation or extra text.'
        logging.info(f'read called with path: {path}, size: {size}, offset: {offset}')
        logging.debug(f'Prompt for OpenAI: {request}')
        current_time = time()
        # Check if the file content is in the cache and not expired
        if path in self.file_cache and current_time - self.file_cache[path]['time'] < self.cache_expiry:
            logging.info(f'Using cached content for path: {path}')
            content = self.file_cache[path]['content']
        else:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [{'role': 'system', 'content': f'{request}'}],
                'max_tokens': 2500
            }
            response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, data=json.dumps(data))
            logging.debug(f'Raw response from OpenAI: {response.text}')
            content = response.json()['choices'][0]['message']['content'].strip()
            # Strip code block delimiters ``` from the start and end of the content
            content = re.sub(r'^```.*\n|```$', '', content)
            logging.info(f'Content received for {path}')
            self.file_cache[path] = {'content': content, 'time': current_time}
        
        return content.encode('utf-8')[offset:offset + size]

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: {} <mountpoint> <api_key>'.format(sys.argv[0]))
        sys.exit(1)
    mountpoint = sys.argv[1]
    api_key = sys.argv[2]
    logging.info(f'Starting FUSE with mountpoint: {mountpoint}')
    FUSE(OpenAIFS(api_key), mountpoint, nothreads=True, foreground=True)