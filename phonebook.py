import psycopg2
import csv
import json
import os
from config import load_config

MENU = """
╔══════════════════════════════════════════╗
║      PhoneBook — Extended (TSIS 1)       ║
╠══════════════════════════════════════════╣
║  Search & Browse                         ║
║  1. Full-text search (name/email/phone)  ║
║  2. Filter contacts by group             ║
║  3. Search contacts by email             ║
║  4. List all contacts (sorted)           ║
║  5. Paginated browse (next/prev/quit)    ║
╠══════════════════════════════════════════╣
║  Manage Contacts                         ║
║  6. Add new contact                      ║
║  7. Add phone to contact (Procedure)     ║
║  8. Move contact to group (Procedure)    ║
║  9. Delete contact                       ║
╠══════════════════════════════════════════╣
║  Import / Export                         ║
║  10. Export contacts to JSON             ║
║  11. Import contacts from JSON           ║
║  12. Import contacts from CSV            ║
╠══════════════════════════════════════════╣
║  0. Exit                                 ║
╚══════════════════════════════════════════╝
"""

def execute_query(query, params=None, fetch=True):
    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                conn.commit()
    except Exception as error:
        print(f"Ошибка БД: {error}")
        return None

def init_database():
    """Автоматически накатывает schema.sql и procedures.sql"""
    print("Инициализация базы данных...")
    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                with open('schema.sql', 'r', encoding='utf-8') as f:
                    cur.execute(f.read())
                with open('procedures.sql', 'r', encoding='utf-8') as f:
                    cur.execute(f.read())
                if os.path.exists('functions.sql'):
                    with open('functions.sql', 'r', encoding='utf-8') as f:
                        cur.execute(f.read())
            conn.commit()
                
        print("База данных успешно обновлена по ТЗ TSIS 1!")
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        

def print_contacts(rows):
    if not rows:
        print("\nКонтакты не найдены.")
        return
    print("\n{:<4} | {:<15} | {:<20} | {:<10} | {:<10} | {:<25}".format("ID", "Name", "Email", "B-Day", "Group", "Phones"))
    print("-" * 95)
    for r in rows:
        c_id = r[0]
        name = f"{r[1]} {r[2] or ''}".strip()
        email = r[3] or '---'
        bday = str(r[4]) if r[4] else '---'
        grp = r[5] or '---'
        phones = r[6] or '---'
        print("{:<4} | {:<15} | {:<20} | {:<10} | {:<10} | {:<25}".format(c_id, name[:15], email[:20], bday, grp[:10], phones[:25]))

# --- SEARCH & BROWSE ---

def search_full_text():
    text = input("Введите текст для поиска (имя, email или телефон): ").strip()
    query = "SELECT * FROM search_contacts(%s::TEXT)"
    rows = execute_query(query, (text,))
    
    if not rows:
        return print("Ничего не найдено.")
    
    print("\n{:<4} | {:<15} | {:<20} | {:<25}".format("ID", "Name", "Email", "Phones"))
    print("-" * 75)
    for r in rows:
        print("{:<4} | {:<15} | {:<20} | {:<25}".format(r[0], f"{r[1]} {r[2] or ''}".strip(), r[3] or '---', r[4] or '---'))

def filter_by_group():
    grp = input("Введите название группы: ").strip()
    query = """
        SELECT c.contact_id, c.first_name, c.last_name, c.email, c.birthday, g.group_name,
               COALESCE(string_agg(p.phone_number, ', '), '') AS phones
        FROM contacts c
        JOIN groups g ON c.group_id = g.group_id
        LEFT JOIN phones p ON c.contact_id = p.contact_id
        WHERE g.group_name ILIKE %s
        GROUP BY c.contact_id, g.group_name
    """
    rows = execute_query(query, (f"%{grp}%",))
    print_contacts(rows)

def search_by_email():
    email = input("Введите часть email: ").strip()
    query = """
        SELECT c.contact_id, c.first_name, c.last_name, c.email, c.birthday, g.group_name, '' AS phones
        FROM contacts c
        LEFT JOIN groups g ON c.group_id = g.group_id
        WHERE c.email ILIKE %s
    """
    rows = execute_query(query, (f"%{email}%",))
    print_contacts(rows)

def list_all_contacts():
    print("Сортировать по: 1) Имени  2) Дню рождения  3) Дате добавления")
    choice = input("Выбор (1-3): ").strip()
    
    order_clause = "c.first_name, c.last_name"
    if choice == '2': order_clause = "c.birthday ASC NULLS LAST"
    elif choice == '3': order_clause = "c.created_at DESC"

    query = f"""
        SELECT c.contact_id, c.first_name, c.last_name, c.email, c.birthday, g.group_name,
               COALESCE(string_agg(p.phone_number || ' (' || p.phone_type || ')', ', '), '') AS phones
        FROM contacts c
        LEFT JOIN groups g ON c.group_id = g.group_id
        LEFT JOIN phones p ON c.contact_id = p.contact_id
        GROUP BY c.contact_id, g.group_name
        ORDER BY {order_clause}
    """
    rows = execute_query(query)
    print_contacts(rows)

def paginated_browse():
    limit = 5
    offset = 0
    query = "SELECT * FROM get_contacts_paginated(%s, %s)"
    
    while True:
        rows = execute_query(query, (limit, offset))
        print_contacts(rows)
        print(f"\nТекущая страница (Смещение: {offset}, Лимит: {limit})")
        
        action = input("Действие: [n]ext - вперед, [p]rev - назад, [q]uit - выход: ").strip().lower()
        if action == 'n':
            if rows and len(rows) == limit: offset += limit
            else: print("Это последняя страница.")
        elif action == 'p':
            if offset >= limit: offset -= limit
            else: print("Это первая страница.")
        elif action == 'q':
            break

# --- MANAGE CONTACTS ---

def add_new_contact():
    fname = input("Имя (обязательно): ").strip()
    if not fname: return print("Имя обязательно!")
    lname = input("Фамилия: ").strip() or None
    email = input("Email: ").strip() or None
    bday = input("День рождения (YYYY-MM-DD): ").strip() or None

    query_insert = """
        INSERT INTO contacts (first_name, last_name, email, birthday) 
        VALUES (%s, %s, %s, %s::DATE) RETURNING contact_id
    """
    try:
        res = execute_query(query_insert, (fname, lname, email, bday))
        print(f"Контакт успешно добавлен! ID: {res[0][0]}")
    except Exception as e:
        print("Ошибка при добавлении:", e)

def call_add_phone():
    name = input("Введите точное ИМЯ контакта: ").strip()
    phone = input("Номер телефона: ").strip()
    ptype = input("Тип (home, work, mobile): ").strip().lower()
    if ptype not in ['home', 'work', 'mobile']:
        return print("Неверный тип! Только home, work, или mobile.")
    
    execute_query("CALL add_phone(%s, %s, %s)", (name, phone, ptype), fetch=False)
    print("Процедура выполнена.")

def call_move_to_group():
    name = input("Введите точное ИМЯ контакта: ").strip()
    group = input("Введите название группы: ").strip()
    execute_query("CALL move_to_group(%s, %s)", (name, group), fetch=False)
    print("Процедура выполнена.")

def delete_contact():
    c_id = input("Введите ID контакта для удаления: ").strip()
    if c_id.isdigit():
        execute_query("DELETE FROM contacts WHERE contact_id = %s", (int(c_id),), fetch=False)
        print("Контакт удален.")

# --- IMPORT / EXPORT ---

def export_json():
    query = """
        SELECT c.first_name, c.last_name, c.email, c.birthday, g.group_name,
               json_agg(json_build_object('phone', p.phone_number, 'type', p.phone_type)) AS phones
        FROM contacts c
        LEFT JOIN groups g ON c.group_id = g.group_id
        LEFT JOIN phones p ON c.contact_id = p.contact_id
        GROUP BY c.contact_id, g.group_name
    """
    rows = execute_query(query)
    data = []
    for r in rows:
        data.append({
            "first_name": r[0], "last_name": r[1], "email": r[2],
            "birthday": str(r[3]) if r[3] else None, "group": r[4],
            "phones": [p for p in r[5] if p.get('phone')] if r[5] else []
        })
        
    with open("contacts_export.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print("Экспортировано в contacts_export.json")

def import_json():
    filename = input("Имя JSON файла: ").strip()
    if not os.path.exists(filename): return print("Файл не найден.")
    
    with open(filename, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
        
    for item in data:
        fname = item.get("first_name")
        if not fname: continue

        # ПРОВЕРКА НА ДУБЛИКАТ
        exists = execute_query("SELECT contact_id FROM contacts WHERE first_name = %s", (fname,))
        if exists:
            choice = input(f"Контакт '{fname}' уже существует. (o - overwrite/перезаписать, s - skip/пропустить): ").strip().lower()
            if choice == 'o':
                execute_query("DELETE FROM contacts WHERE first_name = %s", (fname,), fetch=False)
            else:
                print(f"Пропуск {fname}...")
                continue
                
        # ВСТАВКА КОНТАКТА
        lname = item.get("last_name")
        email = item.get("email")
        bday = item.get("birthday")
        c_id = execute_query("INSERT INTO contacts (first_name, last_name, email, birthday) VALUES (%s, %s, %s, %s::DATE) RETURNING contact_id", 
                             (fname, lname, email, bday))[0][0]
        
        # ГРУППА
        grp = item.get("group")
        if grp:
            execute_query("CALL move_to_group(%s, %s)", (fname, grp), fetch=False)
            
        # ТЕЛЕФОНЫ
        for p in item.get("phones", []):
            ptype = p.get("type", "mobile")
            execute_query("CALL add_phone(%s, %s, %s)", (fname, p.get("phone"), ptype), fetch=False)
            
    print("Импорт из JSON завершен.")

def import_csv():
    filename = input("Имя CSV файла: ").strip()
    if not os.path.exists(filename): return print("Файл не найден.")
    
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        
        rows_processed = 0
        for i, row in enumerate(reader, 1):
            # Агрессивно очищаем названия колонок (ключи) от скрытых символов, пробелов и кавычек
            clean_row = {str(k).strip('\ufeff \t"'): str(v).strip() for k, v in row.items() if k is not None}
            
            # Проверяем, есть ли имя в строке
            fname = clean_row.get('first_name', '')
            if not fname:
                print(f"[-] Строка {i} пропущена (не найдено имя): {clean_row}")
                continue
            
            lname = clean_row.get('last_name', '') or None
            email = clean_row.get('email', '') or None
            
            # Обработка даты (ищем и правильное название, и с опечаткой)
            bday_str = clean_row.get('birthday', '') or clean_row.get('birtthday', '')
            bday = None
            if bday_str:
                if '.' in bday_str:
                    parts = bday_str.split('.')
                    if len(parts) == 3: bday = f"{parts[2]}-{parts[1]}-{parts[0]}"
                else:
                    bday = bday_str
            
            print(f"[+] Читаем контакт: {fname} {lname or ''}")
            
            # Вставляем контакт (если дубликат email - база выдаст ошибку, но скрипт продолжит)
            try:
                execute_query("INSERT INTO contacts (first_name, last_name, email, birthday) VALUES (%s, %s, %s, %s::DATE)", 
                              (fname, lname, email, bday), fetch=False)
            except Exception as e:
                pass # execute_query уже печатает ошибку, так что тут просто идем дальше
            
            # Добавляем группу
            grp = clean_row.get('group', '')
            if grp: 
                execute_query("CALL move_to_group(%s, %s)", (fname, grp), fetch=False)
                
            # Добавляем телефон
            phone = clean_row.get('phone', '')
            ptype = clean_row.get('phone_type', 'mobile')
            if phone: 
                execute_query("CALL add_phone(%s, %s, %s)", (fname, phone, ptype), fetch=False)
                
            rows_processed += 1
            
    print(f"\nИмпорт из CSV завершен. Успешно обработано строк: {rows_processed}")

def main():
    # Автоматически создаем таблицы перед запуском меню (1 раз)
    if input("Сбросить и инициализировать базу из SQL файлов? (y/n): ").strip().lower() == 'y':
        init_database()

    actions = {
        '1': search_full_text, '2': filter_by_group, '3': search_by_email,
        '4': list_all_contacts, '5': paginated_browse, '6': add_new_contact,
        '7': call_add_phone, '8': call_move_to_group, '9': delete_contact,
        '10': export_json, '11': import_json, '12': import_csv
    }

    while True:
        print(MENU)
        choice = input("Select option (0-12): ").strip()
        if choice == '0':
            print("Goodbye!")
            break
        elif choice in actions:
            print("\n" + "="*50)
            actions[choice]()
            print("="*50)
            input("\nPress Enter to return to menu...")
        else:
            print("Invalid choice.")

if __name__ == '__main__':
    main()