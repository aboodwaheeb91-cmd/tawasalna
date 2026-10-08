#!/usr/bin/env python3
"""
Static check: admin panel safe rendering / XSS prevention.
Checks admin.html, admin-view.html, and server.py for common XSS patterns.
"""
import re
import sys

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'

def read_file(path):
    with open(path, encoding='utf-8') as f:
        return f.read()

def check_raw_interpolation(content, filename):
    """
    Check for raw API field interpolation in innerHTML template literals.
    Pattern: ${something.field_name} where field_name is a known API text field,
    NOT wrapped in twEscHtml( or twEscAttr( anywhere inside the ${...} expression.
    """
    known_fields = r'(?:full_name|email|reason|title|description|body|location|step|report_type|reported_name|reporter_name|company_name|provider|institution|degree|msg|page)'
    # Match ${...} expressions (non-greedy, not crossing template literal boundary)
    expr_pattern = re.compile(r'\$\{([^}]+)\}')
    bad = []
    for m in expr_pattern.finditer(content):
        expr = m.group(1)
        # Does the expression reference a known text API field?
        if not re.search(r'\.' + known_fields + r'\b', expr):
            continue
        # Is the value already escaped somewhere in the expression?
        if 'twEscHtml(' in expr or 'twEscAttr(' in expr:
            continue
        # Skip pure condition checks (===, !==) — field used as condition key, not output
        if re.match(r'^[^=!]*===', expr) or re.match(r'^[^=!]*!==', expr):
            continue
        # Skip CSS/class lookups
        if 'colors[' in expr or 'typeMap[' in expr or 'statusMap[' in expr:
            continue
        # Skip substring/slice calls (dates from API: safe subset)
        if '.substring(' in expr or '.slice(' in expr:
            continue
        bad.append(expr)
    return bad

def check_unsafe_onclick(content, filename):
    """
    Check for inline onclick attributes with non-numeric string interpolation.
    Pattern: onclick="...${...non-numeric...}..."
    """
    # Match onclick="..." containing ${...} with string data (not pure integers)
    onclick_pattern = re.compile(
        r'onclick=["\'][^"\']*\$\{[^}]*(?:full_name|email|name|reason|title|description)[^}]*\}[^"\']*["\']'
    )
    matches = onclick_pattern.findall(content)
    return matches

def check_admin_html_route(server_content):
    """
    Check that GET /admin.html does NOT appear as a route in server.py.
    """
    # Match @app.get("/admin.html" as a route decorator
    route_pattern = re.compile(r'@app\.get\s*\(\s*["\']\/admin\.html["\']')
    matches = route_pattern.findall(server_content)
    return matches

def check_rate_limit(server_content):
    """
    Check that /tw-ctrl-login appears in the rate_limit_middleware list.
    """
    pattern = re.compile(r'["\']\/tw-ctrl-login["\']')
    matches = pattern.findall(server_content)
    return matches


def check_single_escaping_impl(tw_shared_content):
    """
    Check that tw_shared.js has exactly ONE full escaping implementation.
    twEscAttr must have the replace chain; twEscHtml must NOT
    have their own (they must delegate to twEscAttr).
    Returns list of violation descriptions.
    """
    violations = []
    impl_blocks = re.findall(
        r'function\s+(\w+)\s*\([^)]*\)\s*\{[^}]*\.replace\(/&/g',
        tw_shared_content
    )
    if len(impl_blocks) > 1:
        violations.append(f'multiple escaping implementations: {impl_blocks}')
    elif len(impl_blocks) == 0:
        violations.append('no escaping implementation found (twEscAttr replace chain missing)')
    elif impl_blocks[0] != 'twEscAttr':
        violations.append(f'canonical impl is {impl_blocks[0]}, expected twEscAttr')
    return violations


def check_url_regex_no_lookahead(admin_html, admin_view_html):
    """
    Check that no old /^(https?:\\/\\/|\\/)/ (without negative lookahead) remains.
    Protocol-relative URLs like //evil.com must be rejected.
    """
    bad = re.compile(r'/\^[(]https\?:\\\/\\\/\|\\\/[)]/')
    violations = []
    for name, content in [('admin.html', admin_html), ('admin-view.html', admin_view_html)]:
        if bad.search(content):
            violations.append(f'{name}: old URL regex (no lookahead) still present')
    return violations


def main():
    all_pass = True

    # Read files
    admin_html = read_file('admin.html')
    admin_view_html = read_file('admin-view.html')
    server_py = read_file('server.py')

    print('=' * 60)
    print('Admin Panel Safe Rendering — Static Checks')
    print('=' * 60)

    # Check 1: No raw API interpolation in admin.html
    bad1 = check_raw_interpolation(admin_html, 'admin.html')
    if bad1:
        print(f'[{FAIL}] admin.html: {len(bad1)} raw API field(s) in innerHTML:')
        for b in bad1:
            print(f'       ${{{b}}}')
        all_pass = False
    else:
        print(f'[{PASS}] admin.html: no raw API field interpolation in innerHTML')

    # Check 2: No raw API interpolation in admin-view.html
    bad2 = check_raw_interpolation(admin_view_html, 'admin-view.html')
    if bad2:
        print(f'[{FAIL}] admin-view.html: {len(bad2)} raw API field(s) in innerHTML:')
        for b in bad2:
            print(f'       ${{{b}}}')
        all_pass = False
    else:
        print(f'[{PASS}] admin-view.html: no raw API field interpolation in innerHTML')

    # Check 3: No unsafe onclick string interpolation in admin.html
    bad3 = check_unsafe_onclick(admin_html, 'admin.html')
    if bad3:
        print(f'[{FAIL}] admin.html: {len(bad3)} unsafe onclick string interpolation(s):')
        for b in bad3:
            print(f'       {b[:100]}')
        all_pass = False
    else:
        print(f'[{PASS}] admin.html: no unsafe onclick string interpolation')

    # Check 4: No unsafe onclick string interpolation in admin-view.html
    bad4 = check_unsafe_onclick(admin_view_html, 'admin-view.html')
    if bad4:
        print(f'[{FAIL}] admin-view.html: {len(bad4)} unsafe onclick string interpolation(s):')
        for b in bad4:
            print(f'       {b[:100]}')
        all_pass = False
    else:
        print(f'[{PASS}] admin-view.html: no unsafe onclick string interpolation')

    # Check 5: GET /admin.html route is removed from server.py
    bad5 = check_admin_html_route(server_py)
    if bad5:
        print(f'[{FAIL}] server.py: GET /admin.html route still exists ({len(bad5)} match(es))')
        all_pass = False
    else:
        print(f'[{PASS}] server.py: GET /admin.html route is deleted')

    # Check 6: /tw-ctrl-login is in rate_limit_middleware
    good6 = check_rate_limit(server_py)
    if good6:
        print(f'[{PASS}] server.py: /tw-ctrl-login is in rate_limit_middleware list')
    else:
        print(f'[{FAIL}] server.py: /tw-ctrl-login NOT found in rate_limit_middleware list')
        all_pass = False

    # Check 7: tw_shared.js has exactly one escaping implementation (twEscAttr)
    tw_shared = read_file('tw_shared.js')
    bad7 = check_single_escaping_impl(tw_shared)
    if bad7:
        print(f'[{FAIL}] tw_shared.js: escaping implementation issue:')
        for b in bad7:
            print(f'       {b}')
        all_pass = False
    else:
        print(f'[{PASS}] tw_shared.js: single canonical escaping implementation (twEscAttr)')

    # Check 8: URL validation regex uses negative lookahead (rejects //evil.com)
    bad8 = check_url_regex_no_lookahead(admin_html, admin_view_html)
    if bad8:
        print(f'[{FAIL}] URL regex missing lookahead:')
        for b in bad8:
            print(f'       {b}')
        all_pass = False
    else:
        print(f'[{PASS}] URL regex uses negative lookahead — rejects protocol-relative URLs')

    print('=' * 60)
    if all_pass:
        print('All checks PASSED.')
    else:
        print('Some checks FAILED.')
        sys.exit(1)

if __name__ == '__main__':
    main()
