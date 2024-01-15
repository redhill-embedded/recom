import sys
import traceback

from recom.cli import cli


def main(argv=None):
    """Main entry point"""

    if argv==None:
        argv = sys.argv

    try:
        return cli(argv[1:])
    except KeyboardInterrupt:
        print("Aborted by user")
    except Exception as e:
        print("FATAL: ", repr(e))
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
    