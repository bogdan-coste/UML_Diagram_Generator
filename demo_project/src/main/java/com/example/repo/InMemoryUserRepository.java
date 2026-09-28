package com.example.repo;

import com.example.model.User;
import java.util.ArrayList;
import java.util.List;

public class InMemoryUserRepository implements UserRepository {
    private List<User> users = new ArrayList<>();

    public User findById(Long id) {
        return users.stream().filter(u -> u.getId().equals(id)).findFirst().orElse(null);
    }

    public List<User> findAll() { return users; }
    public User save(User user) { users.add(user); return user; }
    public void deleteById(Long id) { users.removeIf(u -> u.getId().equals(id)); }
}
