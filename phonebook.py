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
║  7. Add phone to existing contact        ║
║  8. Move contact to group                ║
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

# =========================================================
# ЖЕЛЕЗОБЕТОННАЯ МИГРАЦИЯ БАЗЫ ДАННЫХ НАКОНЕЦ ТО
# =========================================================
def init_database():
    """Обновляет структуру БД: добавляет колонки и переносит телефоны."""
    config = load_config()
    try:
        with psycopg2.connect(**config) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS contacts (
                        contact_id SERIAL PRIMARY KEY,
                        first_name VARCHAR(255) NOT NULL,
                        last_name VARCHAR(255)
                    );
                """)
                
                cur.execute("""
                    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE;
                    ALTER TABLE contacts ADD COLUMN IF NOT EXISTS group_name VARCHAR(100);
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS phones (
                        phone_id SERIAL PRIMARY KEY,
                        contact_id INT REFERENCES contacts(contact_id) ON DELETE CASCADE,
                        phone_number VARCHAR(20) NOT NULL UNIQUE
                    );
                """)

                cur.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_schema='public' AND table_name='contacts' AND column_name='phone'
                        ) THEN
                            -- Копируем телефоны в новую таблицу
                            INSERT INTO phones (contact_id, phone_number)
                            SELECT contact_id, phone FROM contacts WHERE phone IS NOT NULL 
                            ON CONFLICT DO NOTHING;
                            
                            -- Удаляем старую колонку
                            ALTER TABLE contacts DROP COLUMN phone;
                        END IF;
                    END $$;
                """)


                cur.execute("""
                    CREATE OR REPLACE FUNCTION get_contacts_view(
                        p_search_text TEXT DEFAULT NULL,
                        p_group TEXT DEFAULT NULL,
                        p_email TEXT DEFAULT NULL,
                        p_limit INT DEFAULT NULL,
                        p_offset INT DEFAULT 0
                    )
                    RETURNS TABLE (
                        id INT, fname VARCHAR, lname VARCHAR, email VARCHAR, grp VARCHAR, phones TEXT
                    ) AS $$
                    BEGIN
                        RETURN QUERY
                        SELECT 
                            c.contact_id, c.first_name, c.last_name, c.email, c.group_name,
                            COALESCE(string_agg(p.phone_number, ', '), '') AS phones
                        FROM contacts c
                        LEFT JOIN phones p ON c.contact_id = p.contact_id
                        WHERE 
                            (p_search_text IS NULL OR 
                             c.first_name ILIKE '%' || p_search_text || '%' OR 
                             c.last_name ILIKE '%' || p_search_text || '%' OR 
                             c.email ILIKE '%' || p_search_text || '%' OR 
                             p.phone_number ILIKE '%' || p_search_text || '%')
                        AND (p_group IS NULL OR c.group_name ILIKE p_group)
                        AND (p_email IS NULL OR c.email ILIKE '%' || p_email || '%')
                        GROUP BY c.contact_id
                        ORDER BY c.first_name, c.last_name
                        LIMIT p_limit OFFSET p_offset;
                    END;
                    $$ LANGUAGE plpgsql;
                """)

                cur.execute("""
                    CREATE OR REPLACE PROCEDURE add_new_contact(
                        p_fname VARCHAR, p_lname VARCHAR, p_email VARCHAR, p_group VARCHAR, p_phone VARCHAR
                    ) LANGUAGE plpgsql AS $$
                    DECLARE new_contact_id INT;
                    BEGIN
                        INSERT INTO contacts (first_name, last_name, email, group_name)
                        VALUES (p_fname, NULLIF(p_lname, ''), NULLIF(p_email, ''), NULLIF(p_group, ''))
                        RETURNING contact_id INTO new_contact_id;

                        IF p_phone IS NOT NULL AND p_phone != '' THEN
                            INSERT INTO phones (contact_id, phone_number) 
                            VALUES (new_contact_id, p_phone)
                            ON CONFLICT DO NOTHING;
                        END IF;
                    END;
                    $$;
                    
                    CREATE OR REPLACE PROCEDURE add_phone_to_contact(p_contact_id INT, p_phone VARCHAR)
                    LANGUAGE plpgsql AS $$ BEGIN
                        INSERT INTO phones (contact_id, phone_number) VALUES (p_contact_id, p_phone) ON CONFLICT DO NOTHING;
                    END; $$;
                    
                    CREATE OR REPLACE PROCEDURE update_contact_group(p_contact_id INT, p_new_group VARCHAR)
                    LANGUAGE plpgsql AS $$ BEGIN
                        UPDATE contacts SET group_name = NULLIF(p_new_group, '') WHERE contact_id = p_contact_id;
                    END; $$;
                    
                    CREATE OR REPLACE PROCEDURE delete_contact_by_id(p_contact_id INT)
                    LANGUAGE plpgsql AS $$ BEGIN
                        DELETE FROM contacts WHERE contact_id = p_contact_id;
                    END; $$;
                """)
                conn.commit()
    except Exception as error:
        print(f"Критическая ошибка при настройке базы данных: {error}")
        exit(1)

def print_contacts(rows):
    if not rows:
        print("\nКонтакты не найдены.")
        return
    
    print("\n{:<4} | {:<20} | {:<20} | {:<15} | {:<25}".format("ID", "Name", "Email", "Group", "Phones"))
    print("-" * 95)
    for r in rows:
        c_id = r[0]
        name = f"{r[1]} {r[2] or ''}".strip()
        email = r[3] or '---'
        grp = r[4] or '---'
        phones = r[5] or '---'
        print("{:<4} | {:<20} | {:<20} | {:<15} | {:<25}".format(c_id, name[:20], email[:20], grp[:15], phones[:25]))

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

def get_contacts(search=None, group=None, email=None, limit=None, offset=0):
    query = "SELECT * FROM get_contacts_view(%s::TEXT, %s::TEXT, %s::TEXT, %s::INT, %s::INT)"
    return execute_query(query, (search, group, email, limit, offset))

# --- SEARCH & BROWSE ---

def search_full_text():
    text = input("Введите текст для поиска (имя, email или телефон): ").strip()
    rows = get_contacts(search=text)
    print_contacts(rows)

def filter_by_group():
    grp = input("Введите название группы: ").strip()
    rows = get_contacts(group=grp)
    print_contacts(rows)

def search_by_email():
    email = input("Введите часть email: ").strip()
    rows = get_contacts(email=email)
    print_contacts(rows)

def list_all_contacts():
    rows = get_contacts()
    print_contacts(rows)

def paginated_browse():
    limit = 5
    offset = 0
    while True:
        rows = get_contacts(limit=limit, offset=offset)
        print_contacts(rows)
        print(f"\nТекущая страница (Смещение: {offset}, Лимит: {limit})")
        
        action = input("Выберите действие: [n]ext - вперед, [p]rev - назад, [q]uit - выход: ").strip().lower()
        if action == 'n':
            if rows and len(rows) == limit:
                offset += limit
            else:
                print("Это последняя страница.")
        elif action == 'p':
            if offset >= limit:
                offset -= limit
            else:
                print("Это первая страница.")
        elif action == 'q':
            break

# --- MANAGE CONTACTS ---

def add_new_contact():
    fname = input("Имя (обязательно): ").strip()
    if not fname:
        return print("Имя не может быть пустым.")
    lname = input("Фамилия: ").strip() or None
    email = input("Email: ").strip() or None
    grp = input("Группа (Family, Work, etc.): ").strip() or None
    phone = input("Номер телефона: ").strip() or None

    query = "CALL add_new_contact(%s::VARCHAR, %s::VARCHAR, %s::VARCHAR, %s::VARCHAR, %s::VARCHAR)"
    execute_query(query, (fname, lname, email, grp, phone), fetch=False)
    print("Контакт успешно добавлен!")

def add_phone_to_existing():
    c_id = input("Введите ID контакта: ").strip()
    if not c_id.isdigit():
        return print("Неверный ID.")
    phone = input("Введите новый номер телефона: ").strip()
    query = "CALL add_phone_to_contact(%s::INT, %s::VARCHAR)"
    execute_query(query, (int(c_id), phone), fetch=False)
    print("Телефон добавлен.")

def move_to_group():
    c_id = input("Введите ID контакта: ").strip()
    if not c_id.isdigit():
        return print("Неверный ID.")
    grp = input("Введите название новой группы (пусто = удалить из группы): ").strip() or None
    query = "CALL update_contact_group(%s::INT, %s::VARCHAR)"
    execute_query(query, (int(c_id), grp), fetch=False)
    print("Группа обновлена.")

def delete_contact():
    c_id = input("Введите ID контакта для удаления: ").strip()
    if not c_id.isdigit():
        return print("Неверный ID.")
    query = "CALL delete_contact_by_id(%s::INT)"
    execute_query(query, (int(c_id),), fetch=False)
    print("Контакт удален.")

# --- IMPORT / EXPORT ---

def export_json():
    filename = "contacts_export.json"
    rows = get_contacts()
    if not rows:
        return print("Нет данных для экспорта.")
    
    data = []
    for r in rows:
        data.append({
            "id": r[0], "first_name": r[1], "last_name": r[2], 
            "email": r[3], "group": r[4], "phones": r[5].split(', ') if r[5] else []
        })
        
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Контакты успешно экспортированы в {filename}")

def import_json():
    filename = input("Введите имя JSON файла (напр., contacts.json): ").strip()
    if not os.path.exists(filename):
        return print("Файл не найден.")
    
    with open(filename, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            query = "CALL add_new_contact(%s::VARCHAR, %s::VARCHAR, %s::VARCHAR, %s::VARCHAR, %s::VARCHAR)"
            for item in data:
                fname = item.get("first_name", "")
                lname = item.get("last_name", "") or None
                email = item.get("email", "") or None
                grp = item.get("group", "") or None
                phones = item.get("phones", [])
                
                first_phone = phones[0] if phones else None
                execute_query(query, (fname, lname, email, grp, first_phone), fetch=False)
            print("Импорт из JSON завершен.")
        except json.JSONDecodeError:
            print("Ошибка чтения JSON.")

def import_csv():
    filename = input("Введите имя CSV файла (напр., contacts.csv): ").strip()
    if not os.path.exists(filename):
        return print("Файл не найден.")
    
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        query = "CALL add_new_contact(%s::VARCHAR, %s::VARCHAR, %s::VARCHAR, %s::VARCHAR, %s::VARCHAR)"
        for row in reader:
            fname = row.get('first_name', '').strip()
            lname = row.get('last_name', '').strip() or None
            email = row.get('email', '').strip() or None
            grp = row.get('group', '').strip() or None
            phone = row.get('phone', '').strip() or None
            
            if fname:
                execute_query(query, (fname, lname, email, grp, phone), fetch=False)
                count += 1
        print(f"Импорт из CSV завершен. Обработано строк: {count}")

# --- MAIN LOOP ---

def main():
    init_database()

    actions = {
        '1': search_full_text, '2': filter_by_group, '3': search_by_email,
        '4': list_all_contacts, '5': paginated_browse, '6': add_new_contact,
        '7': add_phone_to_existing, '8': move_to_group, '9': delete_contact,
        '10': export_json, '11': import_json, '12': import_csv
    }

    while True:
        print(MENU)
        choice = input("Select option (0-12): ").strip()
        
        if choice == '0':
            print("Goodbye!")
            break
        elif choice in actions:
            print("\n" + "="*40)
            actions[choice]()
            print("="*40)
            input("\nPress Enter to return to menu...")
        else:
            print("Invalid choice. Please select from 0 to 12.")

if __name__ == '__main__':
    main()