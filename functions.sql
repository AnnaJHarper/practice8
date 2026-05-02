
DROP FUNCTION IF EXISTS get_contacts_paginated(INT, INT) CASCADE;
DROP FUNCTION IF EXISTS search_contacts(TEXT) CASCADE;

-- Функция пагинации (из Practice 8)
CREATE OR REPLACE FUNCTION get_contacts_paginated(p_limit INT DEFAULT 10, p_offset INT DEFAULT 0)
RETURNS TABLE (
    contact_id INT, first_name VARCHAR, last_name VARCHAR, 
    email VARCHAR, group_name VARCHAR, phones TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.contact_id, c.first_name, c.last_name, c.email, g.group_name::VARCHAR,
        COALESCE(string_agg(p.phone_number, ', '), '') AS phones
    FROM contacts c
    LEFT JOIN groups g ON c.group_id = g.group_id
    LEFT JOIN phones p ON c.contact_id = p.contact_id
    GROUP BY c.contact_id, g.group_name
    ORDER BY c.first_name, c.last_name
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Универсальная функция поиска (Обновленная для TSIS 1 + Practice 8)
CREATE OR REPLACE FUNCTION search_contacts(p_query TEXT)
RETURNS TABLE (
    id INT, first_name VARCHAR, last_name VARCHAR, email VARCHAR, phones TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.contact_id, c.first_name, c.last_name, c.email, 
        COALESCE(string_agg(p.phone_number || ' (' || p.phone_type || ')', ', '), '') AS phones
    FROM contacts c
    LEFT JOIN phones p ON c.contact_id = p.contact_id
    WHERE 
        c.first_name ILIKE '%' || p_query || '%' OR 
        c.last_name ILIKE '%' || p_query || '%' OR 
        c.email ILIKE '%' || p_query || '%' OR 
        p.phone_number ILIKE '%' || p_query || '%'
    GROUP BY c.contact_id;
END;
$$ LANGUAGE plpgsql;