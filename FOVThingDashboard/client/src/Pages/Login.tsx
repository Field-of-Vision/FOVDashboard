import React from "react";
import LoginForm from "../components/LoginForm";

type Props = { onLogin: (token: string) => void };

export default function LoginPage({ onLogin }: Props) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-600 via-emerald-700 to-emerald-800">
      {/* Stadium Pattern Overlay */}
      <div className="fixed inset-0 opacity-5 pointer-events-none">
        <div 
          className="absolute inset-0" 
          style={{
            backgroundImage: 'radial-gradient(circle at 25% 25%, white 2px, transparent 2px), radial-gradient(circle at 75% 75%, white 2px, transparent 2px)',
            backgroundSize: '50px 50px'
          }}
        />
      </div>

      {/* Logo and Form Container */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen p-8">
        {/* Login Form */}
        <LoginForm onLogin={onLogin} />
      </div>
    </div>
  );
}
