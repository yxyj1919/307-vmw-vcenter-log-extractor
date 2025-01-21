#!/bin/bash

echo "Checking container network settings..."
docker exec vmon-analyzer netstat -tulpn | grep 5000

echo -e "\nChecking container logs..."
docker logs vmon-analyzer | grep -i "running on"

echo -e "\nChecking container accessibility..."
curl -v http://localhost:5000/test 