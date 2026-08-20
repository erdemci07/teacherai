'use client';
import{createContext,useContext,useEffect,useState}from'react';import type{User}from'firebase/auth';import{onAuthStateChanged,signOut}from'firebase/auth';import{getFirebaseAuth,firebaseConfigured}from'../lib/firebase';
type Context={user:User|null;loading:boolean;logout:()=>Promise<void>;token:()=>Promise<string|null>};const AuthContext=createContext<Context|null>(null);
export function AuthProvider({children}:{children:React.ReactNode}){const[user,setUser]=useState<User|null>(null),[loading,setLoading]=useState(firebaseConfigured);useEffect(()=>firebaseConfigured?onAuthStateChanged(getFirebaseAuth(),value=>{setUser(value);setLoading(false)}):()=>undefined,[]);return <AuthContext.Provider value={{user,loading,logout:()=>signOut(getFirebaseAuth()),token:()=>user?user.getIdToken():Promise.resolve(null)}}>{children}</AuthContext.Provider>}
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('AuthProvider gerekli');return value}
export async function currentToken(){if(!firebaseConfigured)return null;return getFirebaseAuth().currentUser?.getIdToken()??null}
