"""
Unit tests for database setup and models.

Verifies that database creation works and tables have correct structure.
"""
import os
import pytest
import tempfile
from sqlmodel import SQLModel, create_engine, Session, select
from core.database import create_db_and_tables, get_database_info
from core.models import UserProfile


@pytest.mark.unit
def test_create_db_and_tables():
    """Test that database and tables are created successfully."""
    # Create database
    create_db_and_tables()
    
    # Verify profiles.db file was created
    assert os.path.exists("profiles.db"), "profiles.db file should be created"
    
    # Verify we can get database info
    info = get_database_info()
    assert info["exists"] is True
    assert info["size_bytes"] > 0
    assert "profiles.db" in info["database_path"]


@pytest.mark.unit
def test_userprofile_model():
    """Test that UserProfile model can be created and saved."""
    from core.database import engine
    
    # Create test profile
    test_profile = UserProfile(
        username="test_user",
        nickname="Test User",
        avatar_url="https://example.com/avatar.jpg",
        source="test",
        priority=1
    )
    
    # Save to database
    with Session(engine) as session:
        session.add(test_profile)
        session.commit()
        
        # Retrieve from database
        statement = select(UserProfile).where(UserProfile.username == "test_user")
        retrieved_profile = session.exec(statement).first()
        
        assert retrieved_profile is not None
        assert retrieved_profile.username == "test_user"
        assert retrieved_profile.nickname == "Test User"
        assert retrieved_profile.source == "test"


if __name__ == "__main__":
    # Run the test
    test_create_db_and_tables()
    test_userprofile_model()
    print("✅ All database tests passed!")