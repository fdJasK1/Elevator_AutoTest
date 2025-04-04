import threading
import time
import glob
import os
from multiprocessing.pool import worker

from colorama import Fore, Back, Style
import error
import generate
import sys
import evaluate
import func_timeout

wrong = 0
tle = 0

def fun(input_str, name, jar_file, interact):
    global wrong
    global tle
    try:
        res, total_power, wt, run_time = evaluate.evaluate(input_str, name)
        if (interact):
            if (res == False):
                print(str(name) + ": " + Fore.RED + "Wrong or TLE" + Fore.WHITE)
                wrong += 1
            else:
                formatted_power = f"{total_power:.1f}"
                formatted_wt = f"{wt:.4f}"
                print(str(name) + ": " + Fore.GREEN + "Accepted" + Fore.WHITE + " with " + str(run_time) + "s")
                print("power costed:         " + str(formatted_power))
                print("average waiting time: " + formatted_wt +"s")
        elif (res == False):
            wrong += 1
    except func_timeout.exceptions.FunctionTimedOut as e:
        tle += 1
        if (interact):
            print(str(os.path.basename(jar_file)) + ": " + Fore.WHITE + "Prase Time Limit Exceeded" + Fore.WHITE)
    except Exception as e:
        wrong += 1
        if (interact):
            print(str(os.path.basename(jar_file)) + ": " + Fore.RED + "Error" + Fore.WHITE)
        error.error_output(name, "Unkown Error", input_str, "", e)


def multi_process(jar_files, interact):
    test_case = 0
    while True:
        test_case += 1
        input_str, command_number = generate.generate_input()

        if (interact):
            print("---->   epoch " + str(test_case) + "   ---   wrong: " + str(wrong) + "   ---   tle: " + str(tle) + "   <----")
            print("input lines:" + str(command_number))

        with open ("stdin.txt", "w") as f:
            f.write(input_str)

        threads = []
        for jar_file in jar_files:
            name = ""
            if (os.name == 'nt'):
                name = os.path.splitext(jar_file)[0].split("\\")[1]
            else:
                name = os.path.splitext(jar_file)[0].split("/")[1]
            
            thread = threading.Thread(target=fun, args = (input_str, name, jar_file, interact))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        if (interact):
            time.sleep(0.75)
            # os.system('cls' if os.name == 'nt' else 'clear')
        else:
            with open ("matcher.log", "w") as f:
                f.write("epoch: " + str(test_case) + " Wrong: " + str(wrong) + " TLE: " + str(tle))

