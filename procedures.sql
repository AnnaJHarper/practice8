CREATE OR REPLACE PROCEDURE upsert_contact(
    p_first_name VARCHAR,
    p_last_name VARCHAR,
    p_phone VARCHAR
)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO contacts (first_name, last_name, phone)
    VALUES (p_first_name, p_last_name, p_phone)
    ON CONFLICT (phone) 
    DO UPDATE SET 
        first_name = EXCLUDED.first_name,
        last_name  = EXCLUDED.last_name;
END;
$$;


CREATE OR REPLACE PROCEDURE delete_user(p_value VARCHAR)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM contacts 
    WHERE first_name = p_value 
       OR last_name  = p_value 
       OR phone      = p_value;
END;
$$;