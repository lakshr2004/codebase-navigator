from parser.tree_parser import extract_routes


# ============================================================
# Test 1: GET route
# ============================================================

def test_extract_get_route():

    content = """
    app.get("/users", getUsers);
    """

    routes = extract_routes(content)

    assert len(routes) == 1

    assert routes[0]["type"] == "route"
    assert routes[0]["method"] == "GET"
    assert routes[0]["route"] == "/users"
    assert routes[0]["handler"] == "getUsers"


# ============================================================
# Test 2: POST route
# ============================================================

def test_extract_post_route():

    content = """
    app.post("/users", createUser);
    """

    routes = extract_routes(content)

    assert len(routes) == 1

    assert routes[0]["method"] == "POST"
    assert routes[0]["route"] == "/users"
    assert routes[0]["handler"] == "createUser"


# ============================================================
# Test 3: Router route
# ============================================================

def test_extract_router_route():

    content = """
    router.get("/profile", getProfile);
    """

    routes = extract_routes(content)

    assert len(routes) == 1

    assert routes[0]["method"] == "GET"
    assert routes[0]["route"] == "/profile"
    assert routes[0]["handler"] == "getProfile"


# ============================================================
# Test 4: Multiple routes
# ============================================================

def test_extract_multiple_routes():

    content = """
    app.get("/users", getUsers);
    app.post("/users", createUser);
    app.delete("/users/:id", deleteUser);
    """

    routes = extract_routes(content)

    assert len(routes) == 3

    assert routes[0]["method"] == "GET"
    assert routes[0]["route"] == "/users"

    assert routes[1]["method"] == "POST"
    assert routes[1]["route"] == "/users"

    assert routes[2]["method"] == "DELETE"
    assert routes[2]["route"] == "/users/:id"


# ============================================================
# Test 5: Unsupported HTTP method
# ============================================================

def test_ignore_unsupported_method():

    content = """
    app.options("/users", optionsHandler);
    """

    routes = extract_routes(content)

    assert routes == []


# ============================================================
# Test 6: Arrow function handler
# ============================================================

def test_arrow_function_handler():

    content = """
    app.get("/health", (req, res) => {
        res.json({ status: "ok" });
    });
    """

    routes = extract_routes(content)

    assert len(routes) == 1

    assert routes[0]["method"] == "GET"
    assert routes[0]["route"] == "/health"
    assert "req" in routes[0]["handler"]
    assert "res" in routes[0]["handler"]


# ============================================================
# Test 7: Route line numbers
# ============================================================

def test_route_line_numbers():

    content = """const app = express();

app.get("/users", getUsers);
"""

    routes = extract_routes(content)

    assert len(routes) == 1

    assert routes[0]["start_line"] == 3
    assert routes[0]["end_line"] == 3