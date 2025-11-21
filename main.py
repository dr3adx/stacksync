import os
import json
import subprocess
import tempfile
import re
from flask import Flask, request, jsonify, abort

app = Flask(__name__)
# Maximum script length for basic input validation
MAX_SCRIPT_SIZE = 16 * 1024 # 16KB

def execute_with_nsjail(script_content):
    MAIN_RETURN_PREFIX = "!MAIN_START!"
    MAIN_RETURN_SUFFIX = "!MAIN_END!"

    # Inject return-capturing boilerplate
    modified_script = f"""\
{script_content}

import sys
import json
import numpy
import pandas
import os

try:
    if 'main' not in globals():
        sys.stderr.write("Error: main() function is missing. Please provide def main() only. Nothing else.")
        sys.exit(1)

    result = main()
    print("{MAIN_RETURN_PREFIX}", json.dumps(result), "{MAIN_RETURN_SUFFIX}", file=sys.stdout, flush=True)

except Exception as e:
    sys.stderr.write(f"Script Execution Error: {{e}}\\n")
    sys.exit(1)
"""

    # Write script into /tmp where Cloud Run allows access
    script_path = "/tmp/script.py"
    with open(script_path, "w") as f:
        f.write(modified_script)

    NSJAIL_CMD = [
        'nsjail',
        '--quiet',
        '--chroot', '/',             
        '--user', 'nobody',
        '--group', 'nogroup',
        '--hostname', 'sandbox',

        # limits
        '--rlimit_as', str(1024 * 1024 * 1024),  # 1GB
        '--rlimit_cpu', '60',
        '--rlimit_fsize', '1024',
        '--rlimit_nofile', '64',

        '--tmpfs', '/tmp:size=25000000',

        '--disable_clone_newns',
        '--disable_clone_newpid',
        '--disable_clone_newuser',
        '--disable_clone_newipc',
        '--disable_clone_newnet',
        '--disable_clone_newcgroup',
        '--disable_clone_newuts',

        '--seccomp_string',
        'KILL { execveat } KILL { fork } KILL { vfork } KILL { ptrace } '
        'KILL { mount } KILL { kexec_file_load } KILL { kexec_load } '
        'KILL { chroot } KILL { setns } DEFAULT ALLOW',

        '--',
        '/usr/local/bin/python3',       # Python inside the container
        script_path                     # script accessible inside jail
    ]

    # Run inside nsjail
    result = subprocess.run(
        NSJAIL_CMD,
        capture_output=True,
        text=True,
        timeout=10,
        check=False
    )

    stdout = result.stdout
    stderr = result.stderr

    # extract main() return JSON
    match = re.search(
        f'{re.escape(MAIN_RETURN_PREFIX)}(.*?){re.escape(MAIN_RETURN_SUFFIX)}',
        stdout,
        re.DOTALL
    )

    if match:
        raw_return = match.group(1).strip()
        stdout = re.sub(
            f'{re.escape(MAIN_RETURN_PREFIX)}.*?{re.escape(MAIN_RETURN_SUFFIX)}\\n?',
            '',
            stdout,
            flags=re.DOTALL
        )
        try:
            main_return_json = json.loads(raw_return)
        except json.JSONDecodeError:
            raise ValueError("Script execution succeeded, but main() did not return valid JSON.")
    else:
        error_message = stderr if stderr else stdout
        raise RuntimeError(
            f"Script execution failed or main() did not return a value. Error: {error_message}"
        )

    return {
        "result": main_return_json,
        "stdout": stdout + stderr
    }

@app.route('/execute', methods=['POST'])
def execute_script():
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400
    
    data = request.get_json()
    
    script = data.get('script')
    if not script or not isinstance(script, str):
        return jsonify({"error": "Missing or invalid 'script' field in JSON body"}), 400

    if len(script) > MAX_SCRIPT_SIZE:
        return jsonify({"error": f"Script size exceeds {MAX_SCRIPT_SIZE} bytes"}), 400

    # handle errors
    try:
        result = execute_with_nsjail(script)
        return jsonify(result), 200

    except ValueError as e:
        # not JSON
        return jsonify({"error": str(e)}), 422
        
    except RuntimeError as e:
        # other errors
        return jsonify({"error": str(e)}), 500
        
    except subprocess.TimeoutExpired:
        # timeout
        return jsonify({"error": "Script execution timed out."}), 408
        
    except Exception as e:
        # unhandled
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)