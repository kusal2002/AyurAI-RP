// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyAKLLwsybraokQrMpwvsl_J6MC68v8KYjw",
  authDomain: "ayurai-39fff.firebaseapp.com",
  databaseURL: "https://ayurai-39fff-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "ayurai-39fff",
  storageBucket: "ayurai-39fff.firebasestorage.app",
  messagingSenderId: "723657712788",
  appId: "1:723657712788:web:4e9bdd4eab12977c2e8081",
  measurementId: "G-52F1F20E2P"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
import { getDatabase } from "firebase/database";
const db = getDatabase(app);

export { app, analytics, db };
