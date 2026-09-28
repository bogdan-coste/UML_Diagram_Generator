package com.example.security;

import com.example.model.User;

public class AuthService {
    public boolean validateToken(String token) {
        return token != null && token.startsWith("Bearer ");
    }

    public User getCurrentUser(String token) {
        return null;
    }
}
