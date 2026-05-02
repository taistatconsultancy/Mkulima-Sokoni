/**
 * Authentication module for Mkulima-Bora
 * Handles Firebase authentication and backend integration
 */

// Firebase configuration from firebase.js
import { initializeApp } from "firebase/app";
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword, 
         signInWithPopup, GoogleAuthProvider, signOut, onAuthStateChanged } from "firebase/auth";

// Use the same config from firebase.js
const firebaseConfig = {
  apiKey: "AIzaSyDEX2PIAw5ZhSp84OiZgRK35WfGhTeT-0E",
  authDomain: "agriculture-43eaf.firebaseapp.com",
  projectId: "agriculture-43eaf",
  storageBucket: "agriculture-43eaf.firebasestorage.app",
  messagingSenderId: "340310533875",
  appId: "1:340310533875:web:54c8b2d5e28bf32d437986",
  measurementId: "G-9W1C0JWRYN"
};

// Initialize Firebase (check if already initialized)
let app, auth, googleProvider;
try {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  googleProvider = new GoogleAuthProvider();
} catch (error) {
  // Firebase already initialized, get existing instance
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  googleProvider = new GoogleAuthProvider();
}

// API base URL - import from config
// For browser environments, we'll define it here if config.js isn't loaded as module
let API_BASE_URL;
if (typeof window !== 'undefined' && window.API_BASE_URL) {
  API_BASE_URL = window.API_BASE_URL;
} else {
  // Fallback: detect environment
  const isProduction = typeof window !== 'undefined' && 
    window.location.hostname !== 'localhost' && 
    window.location.hostname !== '127.0.0.1';
  API_BASE_URL = isProduction ? '/api' : 'http://localhost:5000/api';
}

/**
 * Register user with email and password
 */
async function registerWithEmail(email, password, phoneNumber, role) {
  try {
    // Create user in Firebase
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;
    
    // Register user in backend database
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        firebase_uid: user.uid,
        email: user.email,
        phone_number: phoneNumber,
        role: role
      })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Registration failed');
    }
    
    // Get dashboard route
    const dashboardResponse = await getDashboardRoute(user.uid);
    return {
      success: true,
      user: data.user,
      dashboard: dashboardResponse.dashboard
    };
  } catch (error) {
    console.error('Registration error:', error);
    throw error;
  }
}

/**
 * Login with email and password
 */
async function loginWithEmail(email, password) {
  try {
    // Sign in with Firebase
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const user = userCredential.user;
    const idToken = await user.getIdToken();
    
    // Login to backend
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id_token: idToken
      })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Login failed');
    }
    
    // Handle new user (needs role selection)
    if (data.new_user) {
      return {
        success: true,
        newUser: true,
        firebaseUid: data.firebase_uid,
        email: data.email
      };
    }
    
    // Get dashboard route
    const dashboardResponse = await getDashboardRoute(user.uid);
    return {
      success: true,
      newUser: false,
      user: data.user,
      dashboard: dashboardResponse.dashboard
    };
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
}

/**
 * Sign in with Google
 */
async function signInWithGoogle() {
  try {
    // Sign in with Firebase Google provider
    const result = await signInWithPopup(auth, googleProvider);
    const user = result.user;
    const idToken = await user.getIdToken();
    
    // Check if user exists in backend
    const response = await fetch(`${API_BASE_URL}/auth/google-signin`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        id_token: idToken
      })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Google sign-in failed');
    }
    
    // Handle new user (cold start - needs role selection)
    if (data.new_user) {
      return {
        success: true,
        newUser: true,
        firebaseUid: data.firebase_uid,
        email: data.email
      };
    }
    
    // Get dashboard route for existing user
    const dashboardResponse = await getDashboardRoute(user.uid);
    return {
      success: true,
      newUser: false,
      user: data.user,
      dashboard: dashboardResponse.dashboard
    };
  } catch (error) {
    console.error('Google sign-in error:', error);
    throw error;
  }
}

/**
 * Complete registration for new users (especially Google sign-in)
 */
async function completeRegistration(firebaseUid, email, phoneNumber, role) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/complete-registration`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        firebase_uid: firebaseUid,
        email: email,
        phone_number: phoneNumber,
        role: role
      })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Registration completion failed');
    }
    
    // Get dashboard route
    const dashboardResponse = await getDashboardRoute(firebaseUid);
    return {
      success: true,
      user: data.user,
      dashboard: dashboardResponse.dashboard
    };
  } catch (error) {
    console.error('Complete registration error:', error);
    throw error;
  }
}

/**
 * Get dashboard route based on user role
 */
async function getDashboardRoute(firebaseUid) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/dashboard-route`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        firebase_uid: firebaseUid
      })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Failed to get dashboard route');
    }
    
    return data;
  } catch (error) {
    console.error('Get dashboard route error:', error);
    throw error;
  }
}

/**
 * Logout user
 */
async function logout() {
  try {
    await signOut(auth);
    localStorage.removeItem('user');
    localStorage.removeItem('userRole');
    localStorage.removeItem('authToken');
    window.location.href = '/';
  } catch (error) {
    console.error('Logout error:', error);
    throw error;
  }
}

/**
 * Check authentication state
 */
function onAuthStateChange(callback) {
  onAuthStateChanged(auth, async (user) => {
    if (user) {
      const idToken = await user.getIdToken();
      localStorage.setItem('authToken', idToken);
      callback(user);
    } else {
      localStorage.removeItem('authToken');
      callback(null);
    }
  });
}

/**
 * Get current user
 */
function getCurrentUser() {
  return auth.currentUser;
}

/**
 * Redirect to dashboard based on role
 */
function redirectToDashboard(dashboard) {
  if (dashboard) {
    window.location.href = dashboard;
  } else {
    window.location.href = '/';
  }
}

// Export functions
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    registerWithEmail,
    loginWithEmail,
    signInWithGoogle,
    completeRegistration,
    getDashboardRoute,
    logout,
    onAuthStateChange,
    getCurrentUser,
    redirectToDashboard
  };
}
