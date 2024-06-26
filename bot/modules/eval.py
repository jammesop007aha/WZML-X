#!/usr/bin/env python3
import asyncio
import os
import sys
import textwrap
from io import StringIO
from re import match

async def run_command(cmd: str) -> str:
    """
    Asynchronously run a shell command.

    This function takes a command as a string argument and returns the output of
    the command as a string. It uses asyncio to run the command asynchronously,
    which allows the function to run other tasks while waiting for the command
    to finish executing.

    :param cmd: The command to run.
    :type cmd: str
    :return: The output of the command.
    """
    if len(cmd) > 256:
        raise ValueError("Command length should not exceed 256 characters")

    # Check if the command contains invalid characters
    if not match(r'^\w+(\s+\w+)*$', cmd):
        raise ValueError("Command contains invalid characters")

    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        timeout=60,  # sets a timeout for the command execution
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise asyncio.exceptions.ProcessError(
            cmd, process.returncode, stderr.decode().strip()
        )

    output = stdout.decode().strip()
    return output

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 script.py [command]")
        sys.exit(1)

    cmd = sys.argv[1]

    # Check if the command exists in the system
    if not os.path.exists(os.path.expanduser(f"/usr/bin/{cmd}")):
        print(textwrap.fill(
            f"Error: Command '{cmd}' not found.",
            width=72,
        ))
        sys.exit(1)

    try:
        output = asyncio.run(run_command(cmd))
        print(textwrap.fill(
            f"Command Output:\n{output}",
            width=72,
        ))

    # Handle timeout error
    except asyncio.CancelledError as e:
        print(textwrap.fill(
            "Command execution timed out.",
            width=72,
        ))
        sys.exit(1)

    # Handle ValueError exceptions
    except ValueError as e:
        print(textwrap.fill(
            f"Error: {e}\nUsage: python3 script.py [command]",
            width=72,
        ))
        sys.exit(1)

    # Handle asyncio.exceptions.ProcessError exceptions
    except asyncio.exceptions.ProcessError as e:
        print(textwrap.fill(
            f"Error running command \"{e.cmd}\":\n{e.stderr}",
            width=72,
        ))
        sys.exit(e.returncode)
