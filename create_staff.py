# create_staff.py - Run this to create staff accounts with correct passwords
from db_config import get_db_connection, hash_password

def create_staff_accounts():
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to database")
        return
    
    cursor = conn.cursor()
    
    # Create staff account 1
    username1 = 'staff_john'
    password1 = 'staff123'
    hashed_pw1 = hash_password(password1)
    
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, full_name, is_active)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            password_hash = VALUES(password_hash),
            role = VALUES(role),
            full_name = VALUES(full_name)
        """, (username1, hashed_pw1, 'staff', 'John Staff', True))
        print(f"✅ Staff user '{username1}' created with password '{password1}'")
    except Exception as e:
        print(f"Error creating {username1}: {e}")
    
    # Create staff account 2
    username2 = 'staff_mary'
    password2 = 'staff123'
    hashed_pw2 = hash_password(password2)
    
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, full_name, is_active)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            password_hash = VALUES(password_hash),
            role = VALUES(role),
            full_name = VALUES(full_name)
        """, (username2, hashed_pw2, 'staff', 'Mary Staff', True))
        print(f"✅ Staff user '{username2}' created with password '{password2}'")
    except Exception as e:
        print(f"Error creating {username2}: {e}")
    
    # Update admin password
    admin_password = 'admin123'
    admin_hash = hash_password(admin_password)
    try:
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s 
            WHERE username = 'admin'
        """, (admin_hash,))
        print(f"✅ Admin password updated to '{admin_password}'")
    except Exception as e:
        print(f"Error updating admin: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n" + "="*50)
    print("Staff Accounts Created Successfully!")
    print("="*50)
    print("| Username    | Password  | Role  |")
    print("|-------------|-----------|-------|")
    print("| admin       | admin123  | Admin |")
    print("| staff_john  | staff123  | Staff |")
    print("| staff_mary  | staff123  | Staff |")
    print("="*50)

if __name__ == "__main__":
    create_staff_accounts()