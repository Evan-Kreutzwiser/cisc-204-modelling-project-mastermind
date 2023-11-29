# Mastermind - CISC 204 Modelling Project

This project was built as a term-long project in CISC 204 - Digital Logic.

The goal of this project is to emulate using naterual deduction how a person would play a game of Mastermind. The solver plays the game one guess at a time, using feedback from previous guesses to guide its next answer.

## Gameplay

In a typical game of mastermind, a randomized code of 4 colors is chosen by another person, and the player is tasked with determining the code by making guesses and receiving feedback about how many colors are in the right position and how many are included in the answer but in a different position. Each guess provides the player with more information to work with, and the game is won when a guess matches the code exactly.

## Arguments

The program supports several command line arguments to configure the solver:

* `-q` / `--quiet`: Only print out the final board of a run, omitting the intermediate information and boards
* `-n [N]`: Number of times to play the game (Default: 1)
* `-o [File]` / `--output [File]`: Record the results of each game in a .CSV file (Default: none)
* `-c [2-8]` / `--columns [2-8]`: Set the number of columns in the game board. Can be any value from 2 to 8, inclusive (Default: 4).
* `-a [color 1] [color 2] [...]` / `--answer [color 1] [color 2] [...]`: Set a specific answer for all runs to use (Default: randomized for each run)

## Structure

* `documents`: Contains folders for both of your draft and final submissions. README.md files are included in both.
* `run.py`: General wrapper script that you can choose to use or not. Only requirement is that you implement the one function inside of there for the auto-checks.
* `test.py`: Run this file to confirm that your submission has everything required. This essentially just means it will check for the right files and sufficient theory size.

## Running With Docker

By far the most reliable way to get things running is with [Docker](https://www.docker.com). This section runs through the steps and extra tips to running with Docker. You can remove this section for your final submission, and replace it with a section on how to run your project.

1. First, download Docker https://www.docker.com/get-started

2. Navigate to your project folder on the command line.

3. We first have to build the course image. To do so use the command:
`docker build -t cisc204 .`

4. Now that we have the image we can run the image as a container by using the command: `docker run -it -v $(pwd):/PROJECT cisc204 /bin/bash`

    `$(pwd)` will be the current path to the folder and will link to the container

    `/PROJECT` is the folder in the container that will be tied to your local directory

5. From there the two folders should be connected, everything you do in one automatically updates in the other. For the project you will write the code in your local directory and then run it through the docker command line. A quick test to see if they're working is to create a file in the folder on your computer then use the terminal to see if it also shows up in the docker container.

### Mac Users w/ M1 Chips

If you happen to be building and running things on a Mac with an M1 chip, then you will likely need to add the following parameter to both the build and run scripts:

```
--platform linux/x86_64
```

For example, the build command would become:

```
docker build --platform linux/x86_64 -t cisc204 .
```

### Mount on Different OS'

In the run script above, the `-v $(pwd):/PROJECT` is used to mount the current directory to the container. If you are using a different OS, you may need to change this to the following:

- Windows PowerShell: `-v ${PWD}:/PROJECT`
- Windows CMD: `-v %cd%:/PROJECT`
- Mac: `-v $(pwd):/PROJECT`

Finally, if you are in a folder with a bunch of spaces in the absolute path, then it will break things unless you "quote" the current directory like this (e.g., on Windows CMD):

```
docker run -it -v "%cd%":/PROJECT cisc204
```
