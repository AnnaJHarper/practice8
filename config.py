import os
from configparser import ConfigParser

def load_config(filename='database.ini', section='postgresql'):
    # Узнаем точный путь к папке, где лежит этот скрипт (config.py)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Склеиваем путь к папке с именем файла
    file_path = os.path.join(current_dir, filename)
    
    parser = ConfigParser()
    # Читаем файл по абсолютному пути
    parser.read(file_path)
    
    if parser.has_section(section):
        params = parser.items(section)
        config = {param[0]: param[1] for param in params}
    else:
        raise Exception(f'Section {section} not found in the file: {file_path}')
    
    return config

if __name__ == '__main__':
    config = load_config()
    print(config)