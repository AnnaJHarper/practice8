-- 1. Процедура: Добавить телефон по имени контакта
CREATE OR REPLACE PROCEDURE add_phone(p_contact_name VARCHAR, p_phone VARCHAR, p_type VARCHAR)
LANGUAGE plpgsql AS $$
DECLARE
    v_contact_id INT;
BEGIN
    SELECT contact_id INTO v_contact_id FROM contacts WHERE first_name = p_contact_name LIMIT 1;
    
    IF v_contact_id IS NOT NULL THEN
        INSERT INTO phones (contact_id, phone_number, phone_type) 
        VALUES (v_contact_id, p_phone, p_type) 
        ON CONFLICT (phone_number) DO NOTHING;
    ELSE
        RAISE NOTICE 'Контакт с именем % не найден.', p_contact_name;
    END IF;
END;
$$;

-- 2. Процедура: Переместить контакт в группу (если группы нет - создает её)
CREATE OR REPLACE PROCEDURE move_to_group(p_contact_name VARCHAR, p_group_name VARCHAR)
LANGUAGE plpgsql AS $$
DECLARE
    v_contact_id INT;
    v_group_id INT;
BEGIN
    SELECT contact_id INTO v_contact_id FROM contacts WHERE first_name = p_contact_name LIMIT 1;
    IF v_contact_id IS NULL THEN
        RAISE EXCEPTION 'Контакт с именем % не найден.', p_contact_name;
    END IF;

    -- Создаем группу, если её нет
    INSERT INTO groups (group_name) VALUES (p_group_name) ON CONFLICT (group_name) DO NOTHING;
    
    -- Получаем ID группы
    SELECT group_id INTO v_group_id FROM groups WHERE group_name = p_group_name;

    -- Обновляем контакт
    UPDATE contacts SET group_id = v_group_id WHERE contact_id = v_contact_id;
END;
$$;