"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state
    for name in list(activities.keys()):
        if name in original_activities:
            activities[name]["participants"] = original_activities[name]["participants"].copy()


class TestActivitiesEndpoint:
    """Tests for the /activities endpoint"""
    
    def test_get_activities(self, client):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert isinstance(data, dict)
        assert "Tennis Club" in data
        assert "Basketball Team" in data
        
        # Verify activity structure
        activity = data["Tennis Club"]
        assert "description" in activity
        assert "schedule" in activity
        assert "max_participants" in activity
        assert "participants" in activity
    
    def test_get_activities_has_participants(self, client):
        """Test that activities have participants"""
        response = client.get("/activities")
        data = response.json()
        
        # At least one activity should have participants
        has_participants = any(len(activity["participants"]) > 0 for activity in data.values())
        assert has_participants


class TestSignupEndpoint:
    """Tests for the /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client, reset_activities):
        """Test successful signup for an activity"""
        email = "test@mergington.edu"
        activity_name = "Chess Club"
        
        response = client.post(
            f"/activities/{activity_name}/signup?email={email}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data[activity_name]["participants"]
    
    def test_signup_already_registered(self, client, reset_activities):
        """Test signup fails if student is already registered"""
        email = "alex@mergington.edu"  # Already in Tennis Club
        activity_name = "Tennis Club"
        
        response = client.post(
            f"/activities/{activity_name}/signup?email={email}"
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"].lower()
    
    def test_signup_invalid_activity(self, client):
        """Test signup fails for non-existent activity"""
        email = "test@mergington.edu"
        
        response = client.post(
            "/activities/Nonexistent Activity/signup?email={email}"
        )
        
        assert response.status_code == 404
    
    def test_signup_multiple_participants(self, client, reset_activities):
        """Test that multiple participants can sign up for same activity"""
        activity_name = "Programming Class"
        
        # Sign up first participant
        response1 = client.post(
            f"/activities/{activity_name}/signup?email=student1@mergington.edu"
        )
        assert response1.status_code == 200
        
        # Sign up second participant
        response2 = client.post(
            f"/activities/{activity_name}/signup?email=student2@mergington.edu"
        )
        assert response2.status_code == 200
        
        # Verify both are registered
        activities_response = client.get("/activities")
        participants = activities_response.json()[activity_name]["participants"]
        assert "student1@mergington.edu" in participants
        assert "student2@mergington.edu" in participants


class TestUnregisterEndpoint:
    """Tests for the /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_success(self, client, reset_activities):
        """Test successful unregistration from activity"""
        # First sign up
        email = "newstudent@mergington.edu"
        activity_name = "Robotics Club"
        
        signup_response = client.post(
            f"/activities/{activity_name}/signup?email={email}"
        )
        assert signup_response.status_code == 200
        
        # Then unregister
        unregister_response = client.delete(
            f"/activities/{activity_name}/unregister?email={email}"
        )
        
        assert unregister_response.status_code == 200
        data = unregister_response.json()
        assert "message" in data
        assert email in data["message"]
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data[activity_name]["participants"]
    
    def test_unregister_not_registered(self, client):
        """Test unregister fails if student is not registered"""
        email = "notregistered@mergington.edu"
        activity_name = "Tennis Club"
        
        response = client.delete(
            f"/activities/{activity_name}/unregister?email={email}"
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "not registered" in data["detail"].lower()
    
    def test_unregister_invalid_activity(self, client):
        """Test unregister fails for non-existent activity"""
        response = client.delete(
            "/activities/Nonexistent Activity/unregister?email=test@mergington.edu"
        )
        
        assert response.status_code == 404
    
    def test_unregister_existing_participant(self, client, reset_activities):
        """Test unregistering an existing participant"""
        email = "alex@mergington.edu"  # Already in Tennis Club
        activity_name = "Tennis Club"
        
        # Verify they're registered
        activities_response = client.get("/activities")
        assert email in activities_response.json()[activity_name]["participants"]
        
        # Unregister
        response = client.delete(
            f"/activities/{activity_name}/unregister?email={email}"
        )
        
        assert response.status_code == 200
        
        # Verify they're no longer registered
        activities_response = client.get("/activities")
        assert email not in activities_response.json()[activity_name]["participants"]


class TestAvailabilitySpots:
    """Tests for activity availability calculation"""
    
    def test_availability_decreases_on_signup(self, client, reset_activities):
        """Test that available spots decrease when someone signs up"""
        activity_name = "Debate Team"
        
        # Get initial state
        response = client.get("/activities")
        initial_participants = len(response.json()[activity_name]["participants"])
        
        # Sign up
        client.post(
            f"/activities/{activity_name}/signup?email=newdebater@mergington.edu"
        )
        
        # Check updated state
        response = client.get("/activities")
        updated_participants = len(response.json()[activity_name]["participants"])
        
        assert updated_participants == initial_participants + 1
    
    def test_availability_increases_on_unregister(self, client, reset_activities):
        """Test that available spots increase when someone unregisters"""
        activity_name = "Tennis Club"
        email = "alex@mergington.edu"
        
        # Get initial state
        response = client.get("/activities")
        initial_participants = len(response.json()[activity_name]["participants"])
        
        # Unregister
        client.delete(
            f"/activities/{activity_name}/unregister?email={email}"
        )
        
        # Check updated state
        response = client.get("/activities")
        updated_participants = len(response.json()[activity_name]["participants"])
        
        assert updated_participants == initial_participants - 1
