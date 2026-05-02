-- ВНИМАНИЕ: Очищаем старые таблицы, так как структура меняется
DROP TABLE IF EXISTS phones CASCADE;
DROP TABLE IF EXISTS contacts CASCADE;

-- 1. ТАБЛИЦЫ
CREATE TABLE contacts (
    contact_id SERIAL PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    group_name VARCHAR(100)
);

CREATE TABLE phones (
    phone_id SERIAL PRIMARY KEY,
    contact_id INT REFERENCES contacts(contact_id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL UNIQUE
);

-- 2. ФУНКЦИЯ: Поиск и отображение контактов со всеми телефонами
CREATE OR REPLACE FUNCTION get_contacts_view(
    p_search_text TEXT DEFAULT NULL,
    p_group TEXT DEFAULT NULL,
    p_email TEXT DEFAULT NULL,
    p_limit INT DEFAULT NULL,
    p_offset INT DEFAULT 0
)
RETURNS TABLE (
    id INT,
    fname VARCHAR,
    lname VARCHAR,
    email VARCHAR,
    grp VARCHAR,
    phones TEXT
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

-- 3. ПРОЦЕДУРА: Добавление нового контакта (и сразу первого телефона)
CREATE OR REPLACE PROCEDURE add_new_contact(
    p_fname VARCHAR, p_lname VARCHAR, p_email VARCHAR, p_group VARCHAR, p_phone VARCHAR
) LANGUAGE plpgsql AS $$
DECLARE
    new_contact_id INT;
BEGIN
    INSERT INTO contacts (first_name, last_name, email, group_name)
    VALUES (p_fname, NULLIF(p_lname, ''), NULLIF(p_email, ''), NULLIF(p_group, ''))
    RETURNING contact_id INTO new_contact_id;

    IF p_phone IS NOT NULL AND p_phone != '' THEN
        INSERT INTO phones (contact_id, phone_number) 
        VALUES (new_contact_id, p_phone);
    END IF;
END;
$$;

-- 4. ПРОЦЕДУРА: Добавление телефона к существующему контакту
CREATE OR REPLACE PROCEDURE add_phone_to_contact(p_contact_id INT, p_phone VARCHAR)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO phones (contact_id, phone_number) VALUES (p_contact_id, p_phone);
END;
$$;

-- 5. ПРОЦЕДУРА: Перемещение в группу
CREATE OR REPLACE PROCEDURE update_contact_group(p_contact_id INT, p_new_group VARCHAR)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE contacts SET group_name = NULLIF(p_new_group, '') WHERE contact_id = p_contact_id;
END;
$$;

-- 6. ПРОЦЕДУРА: Удаление контакта (телефоны удалятся автоматически из-за ON DELETE CASCADE)
CREATE OR REPLACE PROCEDURE delete_contact_by_id(p_contact_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM contacts WHERE contact_id = p_contact_id;
END;
$$;