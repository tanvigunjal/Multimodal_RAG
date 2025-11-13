#!/bin/bash
# Comprehensive testing script for Multimodal RAG deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_section() { echo -e "\n${BLUE}▶${NC} $1\n$(printf '=%.0s' {1..50})"; }

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name=$1
    local test_command=$2
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if eval "$test_command" &>/dev/null; then
        print_success "$test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        print_error "$test_name"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

echo "=========================================="
echo "  Multimodal RAG - Deployment Tests"
echo "=========================================="
echo ""

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
print_info "Testing with IP: $PUBLIC_IP"

# Determine docker compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# ==========================================
# 1. PREREQUISITES TESTS
# ==========================================
print_section "1. Prerequisites Check"

run_test "Docker is installed" "command -v docker"
run_test "Docker Compose is installed" "command -v docker-compose || docker compose version"
run_test ".env file exists" "test -f .env"
run_test "docker-compose.yml exists" "test -f docker-compose.yml"

# ==========================================
# 2. DOCKER CONTAINERS TESTS
# ==========================================
print_section "2. Docker Containers Status"

run_test "Backend container is running" "$COMPOSE_CMD ps backend | grep -q 'Up'"
run_test "Frontend container is running" "$COMPOSE_CMD ps frontend | grep -q 'Up'"
run_test "Qdrant container is running" "$COMPOSE_CMD ps qdrant | grep -q 'Up'"

# ==========================================
# 3. NETWORK CONNECTIVITY TESTS
# ==========================================
print_section "3. Network & Port Tests"

run_test "Backend port 8000 is listening" "nc -z localhost 8000"
run_test "Frontend port 8081 is listening" "nc -z localhost 8081"
run_test "Qdrant port 6333 is listening" "nc -z localhost 6333"

# ==========================================
# 4. HEALTH ENDPOINT TESTS
# ==========================================
print_section "4. Health Endpoint Tests"

# Backend health check
if curl -s -f http://localhost:8000/healthz > /dev/null 2>&1; then
    RESPONSE=$(curl -s http://localhost:8000/healthz)
    if echo "$RESPONSE" | grep -q "ok"; then
        print_success "Backend /healthz endpoint returns OK"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_error "Backend /healthz endpoint returns unexpected response"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
else
    print_error "Backend /healthz endpoint not accessible"
    FAILED_TESTS=$((FAILED_TESTS + 1))
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
fi

# Qdrant health check
if curl -s -f http://localhost:6333/healthz > /dev/null 2>&1; then
    print_success "Qdrant health endpoint accessible"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_error "Qdrant health endpoint not accessible"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Frontend accessibility
if curl -s -f http://localhost:8081 > /dev/null 2>&1; then
    print_success "Frontend is accessible"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_error "Frontend is not accessible"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# ==========================================
# 5. API ENDPOINT TESTS
# ==========================================
print_section "5. API Endpoint Tests"

# Test API documentation
if curl -s -f http://localhost:8000/docs > /dev/null 2>&1; then
    print_success "API documentation (/docs) accessible"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_warning "API documentation (/docs) not accessible (may be disabled)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test OpenAPI schema
if curl -s -f http://localhost:8000/openapi.json > /dev/null 2>&1; then
    print_success "OpenAPI schema accessible"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_warning "OpenAPI schema not accessible"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# ==========================================
# 6. AUTHENTICATION TESTS
# ==========================================
print_section "6. Authentication Tests"

# Test login endpoint exists (should return 422 without body)
LOGIN_RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null http://localhost:8000/v1/auth/login)
if [ "$LOGIN_RESPONSE" = "422" ] || [ "$LOGIN_RESPONSE" = "401" ]; then
    print_success "Login endpoint is responding"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_error "Login endpoint not responding correctly (got $LOGIN_RESPONSE)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# ==========================================
# 7. FIREWALL TESTS
# ==========================================
print_section "7. Firewall Configuration"

# Check iptables rules
if sudo iptables -L INPUT -n 2>/dev/null | grep -q "dpt:80\|dpt:8081\|dpt:8000"; then
    print_success "Firewall rules configured (iptables)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_warning "Firewall rules not found in iptables (may use firewalld)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Check firewalld if available
if command -v firewall-cmd &> /dev/null; then
    if sudo firewall-cmd --list-ports 2>/dev/null | grep -q "80/tcp\|8081/tcp\|8000/tcp"; then
        print_success "Firewall rules configured (firewalld)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_warning "Firewall rules not found in firewalld"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
fi

# ==========================================
# 8. ENVIRONMENT CONFIGURATION TESTS
# ==========================================
print_section "8. Environment Configuration"

if [ -f ".env" ]; then
    # Check for critical environment variables
    if grep -q "GOOGLE_API_KEY=" .env && ! grep -q "GOOGLE_API_KEY=$" .env; then
        print_success "GOOGLE_API_KEY is set"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_warning "GOOGLE_API_KEY not set in .env"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if grep -q "JWT_SECRET_KEY=" .env && ! grep -q "JWT_SECRET_KEY=$" .env; then
        print_success "JWT_SECRET_KEY is set"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_warning "JWT_SECRET_KEY not set in .env"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
fi

# ==========================================
# 9. EXTERNAL ACCESSIBILITY TESTS
# ==========================================
print_section "9. External Accessibility (if deployed)"

if [ "$PUBLIC_IP" != "localhost" ]; then
    print_info "Testing external access on $PUBLIC_IP..."
    
    # Test external frontend access
    if timeout 5 curl -s -f http://$PUBLIC_IP:8081 > /dev/null 2>&1; then
        print_success "Frontend accessible externally at http://$PUBLIC_IP:8081"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_warning "Frontend not accessible externally (check Oracle Cloud Security List)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    # Test external backend access
    if timeout 5 curl -s -f http://$PUBLIC_IP:8000/healthz > /dev/null 2>&1; then
        print_success "Backend accessible externally at http://$PUBLIC_IP:8000"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        print_warning "Backend not accessible externally (check Oracle Cloud Security List)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
else
    print_info "Skipping external tests (localhost detected)"
fi

# ==========================================
# 10. DOCKER LOGS CHECK
# ==========================================
print_section "10. Docker Logs Analysis"

# Check for errors in backend logs
BACKEND_ERRORS=$($COMPOSE_CMD logs backend 2>&1 | grep -i "error\|exception\|failed" | wc -l)
if [ "$BACKEND_ERRORS" -eq 0 ]; then
    print_success "No errors in backend logs"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    print_warning "Found $BACKEND_ERRORS error entries in backend logs"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# ==========================================
# SUMMARY
# ==========================================
echo ""
echo "=========================================="
echo "  Test Summary"
echo "=========================================="
echo ""
echo "Total Tests:  $TOTAL_TESTS"
echo -e "${GREEN}Passed:       $PASSED_TESTS${NC}"
echo -e "${RED}Failed:       $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Your application is ready for use:"
    if [ "$PUBLIC_IP" != "localhost" ]; then
        echo "  Frontend: http://$PUBLIC_IP:8081"
        echo "  Backend:  http://$PUBLIC_IP:8000"
        echo "  API Docs: http://$PUBLIC_IP:8000/docs"
    else
        echo "  Frontend: http://localhost:8081"
        echo "  Backend:  http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
    fi
    exit 0
else
    echo -e "${YELLOW}⚠ Some tests failed${NC}"
    echo ""
    echo "Common issues:"
    echo "  • External access failing: Configure Oracle Cloud Security List"
    echo "  • Services not running: Run 'docker-compose up -d'"
    echo "  • Environment variables: Check .env file"
    echo "  • View logs: docker-compose logs -f"
    echo ""
    exit 1
fi
