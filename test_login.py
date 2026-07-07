# test_login.py
from db_config import get_db_connection, check_password, hash_password

def test():
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to database!")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    # Get admin user
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    user = cursor.fetchone()
    
    if not user:
        print("❌ Admin user NOT FOUND in database!")
        print("Please run the SQL to create users first.")
        return
    
    print("=" * 50)
    print(f"✅ User found: {user['username']}")
    print(f"   Role: {user['role']}")
    print(f"   Active: {user.get('is_active', 'Unknown')}")
    print(f"   Password Hash: {user['password_hash'][:30]}...")
    print("=" * 50)
    
    # Test different passwords
    passwords_to_test = ['admin123', 'Admin123', 'password', 'admin']
    
    print("\n🔍 Testing passwords:")
    print("-" * 30)
    
    for pwd in passwords_to_test:
        result = check_password(pwd, user['password_hash'])
        print(f"   Password '{pwd}': {'✅ MATCHES' if result else '❌ Does NOT match'}")
    
    print("=" * 50)
    
    # Create a new test user with a fresh hash
    print("\n🔧 Creating a test user with fresh hash...")
    
    fresh_hash = hash_password('test123')
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, full_name, is_active)
        VALUES (%s, %s, %s, %s, %s)
    """, ('testuser', fresh_hash, 'admin', 'Test User', True))
    conn.commit()
    
    # Test the new user
    cursor.execute("SELECT * FROM users WHERE username = 'testuser'")
    test_user = cursor.fetchone()
    
    if test_user:
        result = check_password('test123', test_user['password_hash'])
        print(f"   Test user 'testuser' with password 'test123': {'✅ WORKS!' if result else '❌ FAILED!'}")
    
    print("=" * 50)
    print("\n📝 Try logging in with these credentials:")
    print("   Username: testuser")
    print("   Password: test123")
    print("=" * 50)
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    test()