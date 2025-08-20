Application for creating traffic incidents and deploying traffic management actions inside a microscopic simulation via the Aimsun Next API.


# Setup

This application has several dependencies. Although the application itself is run using the Aimsun Next embedded Python interpreter, you still need the packages compiled on your machine, for which you need to:

Install Python 3.10

Install application dependencies, if you have python 3 installed on your machine, this can be achieved via the command: `python -m pip install -r requirements.txt`, which will install all the required dependencies.

After the install pip should show where the installation was saved. Now for the embedded interpreter to know, where to look for packages you need to create an enviromental variable called **PYTHONPATH** and set it to the path where the python libraries were installed (if you missed it you can just install a random module via python -m pip install, grab the path and uninstall the random module).

If all steps are completed, the Aimsun Next embedded interpreter should be able to find the application dependencies and you are free to use the application.


# Usage

This application is designed to work with any microscopic model inside Aimsun Next (as of now at least for version 23.0.2).

1. Inside Aimsun Next open your model with the microscopic scenario for which you want to use the application.

2. Once open click on **Scenarios>Properties**, this should open a dialog window, in which you should see a tab called **Aimsun Next APIs**

3. Inside the Aimsun Next APIs window there should be a List with the caption **Aimsun Next APIs**, click on the button **Add** and locate the file *aimsun_entrypoint.py* on your machine (note that the application requires all of the files, even though Aimsun will copy the aimsun_entrypoint.py inside its *Scripts* folder, keep using the original one which can access all of its modules *or you might be able to copy the whole application into the scripts folder*).

4. Once you have assigned the *aimsun_entrypoint.py* to the scenarion, any experiments / replications run with the scenario should integrate with the *tcon* application.

5. Now you can either define schedule files or affect the application via the REST API


# Documentation

To discover which commands are supported by the application, you can look at the **docs/** folder, which contains the documentation for application commands in JSON and HTML formats.

If you want to regenerate the documentation yourself, you first need to install the dependencies for generating the docs: ``python -m pip install -r requirements.doc.txt``

After which you can run: ``python -m tools.doc -o`` (the -o flag will just open the generated documentation in your browser). And you will have generated the documentation yourself.

**The commands documented inside the docs/ folder are supported when configuring via config files, for REST API documentation visit the API with the /docs suffix e.g.:** ```localhost:8000/docs```


# Configuration
The application supports configuration via config files, on init the application searches its root directory for a file called **config.{yaml, yml, json}** in which you can specify (you can view the config.example file to see what can be configured):

- ## Rest API settings:
    ```yaml
    api:
      host: 127.0.0.1
      port: 8000
    ```

    Allows setting the host and port of the REST API server process. (this is the address where you can also find the documentation for the API via the /docs suffix)

- ## Logging facilities:
    Allows configuring global and per-module log levels, the modules correspond to file names, so if we want to modify the logging level for ```server/api.py```, the module is simply called ```server.api```.
    The one exception is ```aimsun_entrypoint.py```, for which the module is called ```aimsun.entrypoint```
    ```yaml
    log:
      level: INFO
      ansi: false
      modules:
        aimsun.entrypoint:
          level: DEBUG
          ansi: false
          logfile: null
        server.ipc:
          level: INFO
          ansi: false
          logfile: null
        server.api:
          level: INFO
          ansi: true
          logfile: null
        common.config:
          level: INFO
          ansi: false
          logfile: null
    ```
    Global config without a specified module is the default which applies to all modules (and is overriden if settings are specified for a module).

    Values that can be set are:

    ```level:``` Log level

    ```logfile:``` Relative or absolute path of the logfile.

    ```ansi:``` Whether logging should use ANSI escape sequences to colorize the output

- ## Scheduling:
    Scheduling is supported via two mechanisms: inline schedule (defined directly in config.json via the key ```schedule```) or by defining the schedule in one or more files for which only the paths are necessary.

    If you only wish to define a single external file, this can be achieved via the key ```schedule_file``` which accepts a relative or absolute path to the schedule file (again yaml, yml or json)

    If you wish to provide a list of schedule files, this can be achieved via the key ```schedule_files```, which accepts a list of paths

    The schedules are processed in the order they are encountered and them merged into one, which means you can define the schedule using all three variants and they will all be merged into a single internal schedule.

    For the list of commands which are accepted in the schedule definition and for their parameters see the provided (or generated) documentation.

    - Example of defining a schedule file:
        ```yml
        schedule_file: schedules/example.yml
        ```

    - Example of direct schedule definition:
        ```yml
        schedule:
        - command: measure_create
            time: 60
            payload:
            type: speed_section
            id_action: 10
            duration: 600
            section_ids: [501]
            speed: 5
        - command: measure_remove
            time: 70
            payload:
            id_action: 10
        - command: measure_remove
            time: 80
            payload:
            id_action: 10
        ```
