package com.example.service;

import com.example.model.User;
import com.example.repo.UserRepository;
import com.example.security.AuthService;
import java.util.List;

public class UserService extends BaseService {
    private UserRepository userRepo;
    private AuthService authService;

    public UserService(UserRepository userRepo, AuthService authService) {
        this.userRepo = userRepo;
        this.authService = authService;
    }

    public User getUserById(Long id, String token) {
        if (!authService.validateToken(token)) throw new RuntimeException("Unauthorized");
        return userRepo.findById(id);
    }

    public List<User> listAll(String token) {
        if (!authService.validateToken(token)) throw new RuntimeException("Unauthorized");
        return userRepo.findAll();
    }

    public User createUser(User user, String token) {
        if (!authService.validateToken(token)) throw new RuntimeException("Unauthorized");
        return userRepo.save(user);
    }

    public void deleteUser(Long id, String token) {
        if (!authService.validateToken(token)) throw new RuntimeException("Unauthorized");
        userRepo.deleteById(id);
    }

    public User updateUser(Long id, User user, String token) {
        return userRepo.save(user);
    }
}
