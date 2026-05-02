CREATE OR REPLACE FUNCTION search_contacts(pattern_text TEXT)
RETURNS TABLE (
    contact_id INT,
    first_name VARCHAR,
    last_name VARCHAR,
    phone VARCHAR
)
AS $$
BEGIN
    RETURN QUERY
    SELECT c.contact_id, c.first_name, c.last_name, c.phone
    FROM contacts c
    WHERE c.first_name ILIKE '%' || pattern_text || '%'
       OR c.last_name  ILIKE '%' || pattern_text || '%'
       OR c.phone      ILIKE '%' || pattern_text || '%'
    ORDER BY c.first_name, c.last_name;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION get_contacts_paginated(p_limit INT DEFAULT 10, p_offset INT DEFAULT 0)
RETURNS TABLE (
    contact_id INT,
    first_name VARCHAR,
    last_name VARCHAR,
    phone VARCHAR
)
AS $$
BEGIN
    RETURN QUERY
    SELECT c.contact_id, c.first_name, c.last_name, c.phone
    FROM contacts c
    ORDER BY c.first_name, c.last_name
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;


-- Массовый insert лучше сделать как PROCEDURE (как просили в задании)
CREATE OR REPLACE PROCEDURE insert_many_users(
    p_first_names TEXT[], 
    p_last_names TEXT[], 
    p_phones TEXT[],
    OUT bad_records TEXT
)
AS $$
DECLARE
    i INT;
    fname TEXT;
    lname TEXT;
    ph TEXT;
    errors TEXT[] := ARRAY[]::TEXT[];
BEGIN
    FOR i IN 1 .. LEAST(array_length(p_phones, 1), array_length(p_first_names, 1))
    LOOP
        fname := trim(COALESCE(p_first_names[i], ''));
        lname := NULLIF(trim(COALESCE(p_last_names[i], '')), '');
        ph    := trim(COALESCE(p_phones[i], ''));

        IF ph ~ '^[0-9+\-\s()]+$' AND length(ph) >= 5 THEN   -- улучшенная валидация
            INSERT INTO contacts (first_name, last_name, phone)
            VALUES (fname, lname, ph)
            ON CONFLICT (phone) DO UPDATE 
                SET first_name = EXCLUDED.first_name,
                    last_name  = EXCLUDED.last_name;
        ELSE
            errors := array_append(errors, 
                format('(%s %s, %s)', fname, COALESCE(lname,''), ph));
        END IF;
    END LOOP;

    bad_records := array_to_string(errors, '; ');
END;
$$ LANGUAGE plpgsql;