Hello and welcome to the python sandboxed script execution project!



INSTRUCTIONS:

1\) Run it localy: `docker build -t pythontest .; docker run -d -p 8080:8080 pythontest`

2\) NSJail doesn't work on Google Cloud Run due to iVisor and due to sandbox inside sandbox and I've tested several variations (see commits)

3\) Example CURL: `curl -X POST "http://127.0.0.1:8080/execute" \\

&nbsp;    -H "Content-Type: application/json" \\

&nbsp;    -d '{"script": "def main(): print(\\"Executing...\\"); return \\"WORKS\\""}'`









