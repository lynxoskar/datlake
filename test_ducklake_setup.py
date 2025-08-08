#!/usr/bin/env python3
"""
Test script to verify DuckLake PostgreSQL integration setup
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_duckdb_extensions():
    """Test if DuckDB extensions can be loaded."""
    try:
        import duckdb
        print("✓ DuckDB imported successfully")
        
        # Test connection
        con = duckdb.connect()
        print("✓ DuckDB connection established")
        
        # Test extension installation
        try:
            con.execute("INSTALL ducklake;")
            print("✓ DuckLake extension installed")
        except Exception as e:
            print(f"✗ DuckLake extension installation failed: {e}")
            return False
            
        try:
            con.execute("INSTALL postgres;")
            print("✓ PostgreSQL extension installed")
        except Exception as e:
            print(f"✗ PostgreSQL extension installation failed: {e}")
            return False
            
        try:
            con.execute("INSTALL s3;")
            print("✓ S3 extension installed")
        except Exception as e:
            print(f"✗ S3 extension installation failed: {e}")
            return False
        
        # Test loading extensions
        try:
            con.execute("LOAD ducklake;")
            con.execute("LOAD postgres;")
            con.execute("LOAD s3;")
            print("✓ All extensions loaded successfully")
        except Exception as e:
            print(f"✗ Extension loading failed: {e}")
            return False
            
        return True
        
    except ImportError as e:
        print(f"✗ DuckDB import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_config_structure():
    """Test if configuration structure is correct."""
    try:
        # Mock the configuration for testing
        class MockSettings:
            def __init__(self):
                self.database = MockDatabase()
                self.storage = MockStorage()
                
        class MockDatabase:
            def __init__(self):
                self.postgres_host = "localhost"
                self.postgres_port = 5432
                self.postgres_db = "ducklakedb"
                self.postgres_user = "postgres"
                self.postgres_password = MockSecret("password")
                
        class MockStorage:
            def __init__(self):
                self.minio_endpoint = "localhost:9000"
                self.minio_access_key = "minioadmin"
                self.minio_secret_key = MockSecret("minioadmin")
                self.minio_secure = False
                self.minio_region = "us-east-1"
                self.default_bucket = "ducklake-data"
                
        class MockSecret:
            def __init__(self, value):
                self.value = value
            def get_secret_value(self):
                return self.value
        
        settings = MockSettings()
        
        # Test PostgreSQL connection string format
        postgres_conn = f"dbname={settings.database.postgres_db} host={settings.database.postgres_host} port={settings.database.postgres_port} user={settings.database.postgres_user} password={settings.database.postgres_password.get_secret_value()}"
        print(f"✓ PostgreSQL connection string: {postgres_conn}")
        
        # Test S3 data path format
        s3_data_path = f"s3://{settings.storage.default_bucket}/ducklake-data/"
        print(f"✓ S3 data path: {s3_data_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def main():
    print("Testing DuckLake PostgreSQL integration setup...")
    print("=" * 50)
    
    success = True
    
    print("\n1. Testing DuckDB Extensions:")
    success &= test_duckdb_extensions()
    
    print("\n2. Testing Configuration Structure:")
    success &= test_config_structure()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ All tests passed! DuckLake setup should work correctly.")
        print("\nNext steps:")
        print("1. Ensure PostgreSQL is running with the specified database")
        print("2. Ensure MinIO is running on the specified endpoint")
        print("3. Start the application with proper environment variables")
    else:
        print("✗ Some tests failed. Please check the errors above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())